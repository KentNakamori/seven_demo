"""
セブン銀行 AI校閲支援ツール（デモ版）

Streamlit アプリ本体。
ファイルアップロード → Gemini API で校閲 → レポート表示。
"""

import streamlit as st
from PIL import Image
from dotenv import load_dotenv

from api_client import configure_api, run_proofread, REFERENCE_FILES, REFERENCES_DIR
from prompt_builder import build_prompt
from report_generator import parse_report, wrap_report, generate_filename

# .env 読み込み
load_dotenv()

# --- ページ設定 ---
st.set_page_config(
    page_title="セブン銀行 AI校閲支援ツール",
    page_icon="📋",
    layout="wide",
)

# --- カスタムCSS ---
st.markdown("""
<style>
/* サマリカード */
.summary-card {
    padding: 1.5rem;
    border-radius: 12px;
    text-align: center;
    margin-bottom: 1rem;
}
.summary-fail {
    background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
    border: 2px solid #ef4444;
}
.summary-warning {
    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
    border: 2px solid #f59e0b;
}
.summary-info {
    background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
    border: 2px solid #3b82f6;
}
.summary-ok {
    background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
    border: 2px solid #10b981;
}
.summary-number {
    font-size: 3rem;
    font-weight: bold;
    margin: 0;
}
.summary-label {
    font-size: 1rem;
    color: #666;
    margin-top: 0.5rem;
}

/* 指摘カード */
.issue-card {
    padding: 1rem 1.5rem;
    border-radius: 8px;
    margin-bottom: 0.75rem;
    border-left: 4px solid;
}
.issue-fail {
    background-color: #fef2f2;
    border-left-color: #ef4444;
}
.issue-warning {
    background-color: #fffbeb;
    border-left-color: #f59e0b;
}
.issue-info {
    background-color: #eff6ff;
    border-left-color: #3b82f6;
}
.issue-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
}
.issue-badge {
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: bold;
    color: white;
}
.badge-fail { background-color: #ef4444; }
.badge-warning { background-color: #f59e0b; }
.badge-info { background-color: #3b82f6; }
.issue-content {
    font-size: 1rem;
    color: #1f2937;
    margin-bottom: 0.5rem;
}
.issue-meta {
    font-size: 0.85rem;
    color: #6b7280;
}

/* セクション */
.section-header {
    padding: 0.75rem 1rem;
    background: #f3f4f6;
    border-radius: 8px;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* 目視確認 */
.visual-check {
    padding: 0.75rem 1rem;
    background: #fef9c3;
    border: 1px solid #facc15;
    border-radius: 8px;
    margin-bottom: 0.5rem;
    color: #713f12;
    font-weight: 500;
}

/* 成功メッセージ */
.success-message {
    padding: 1.5rem;
    background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
    border: 2px solid #10b981;
    border-radius: 12px;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# --- サイドバー ---
with st.sidebar:
    st.header("⚙ 設定")

    st.subheader("参照ファイル一覧")
    for fname in REFERENCE_FILES:
        st.text(f"・{fname}")

    st.subheader("ルールファイル")
    st.text("・rules/rules.yaml")

    st.divider()

    st.subheader("API設定")
    model_name = st.selectbox(
        "Model",
        ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"],
        index=0,
        help="2.5-pro（推奨）は高精度。Flash系は高速だが精度が低い。"
    )

    st.divider()

    # 詳細表示オプション
    show_raw = st.checkbox("生のMarkdownも表示", value=False)

# --- メインエリア ---
st.title("📋 セブン銀行 AI校閲支援ツール（デモ）")

# ファイルアップロード
uploaded_file = st.file_uploader(
    "チェック対象ファイル",
    type=["png", "jpg", "jpeg"],
    help="PNG / JPG 形式の告知物画像をアップロードしてください",
)

# チェック項目の選択
st.subheader("チェック項目")
col1, col2 = st.columns(2)
with col1:
    chk_atm = st.checkbox("ATM画像チェック（種類・禁則）", value=True)
    chk_logo = st.checkbox("ロゴチェック（形・色・サイズ・余白）", value=True)
with col2:
    chk_wording = st.checkbox("表記・ワーディングチェック", value=True)
    chk_format = st.checkbox("形式チェック（日付・金額・免責）", value=True)

# アップロード画像のプレビュー
if uploaded_file is not None:
    image = Image.open(uploaded_file)
    with st.expander("📷 アップロード画像プレビュー", expanded=False):
        st.image(image, use_container_width=True)

# --- 校閲実行 ---
if st.button("▶ 校閲を実行", type="primary", disabled=uploaded_file is None):
    # API 設定チェック
    try:
        configure_api()
    except ValueError as e:
        st.error(f"❌ API設定エラー: {e}")
        st.stop()

    # 参照画像の存在チェック
    for fname in REFERENCE_FILES:
        if not (REFERENCES_DIR / fname).exists():
            st.error(f"❌ 参照画像が見つかりません: references/{fname}")
            st.stop()

    check_items = {
        "atm": chk_atm,
        "logo": chk_logo,
        "wording": chk_wording,
        "format": chk_format,
    }

    prompt_text = build_prompt(check_items)
    image = Image.open(uploaded_file)

    with st.spinner("🔍 校閲を実行中... Gemini API に問い合わせています"):
        try:
            result_text = run_proofread(
                target_image=image,
                prompt_text=prompt_text,
                model_name=model_name,
            )
        except Exception as e:
            st.error(f"❌ API呼び出しエラー: {e}")
            st.stop()

    # レポートをパース
    report = parse_report(result_text)

    # --- 結果表示（ポップアップ風モーダル） ---
    st.divider()

    # 結果ヘッダー
    total_issues = report.summary["Fail"] + report.summary["Warning"]
    if total_issues == 0:
        st.markdown("""
        <div class="success-message">
            <h2 style="margin:0; color:#059669;">✅ 校閲完了 - 問題は見つかりませんでした</h2>
            <p style="margin:0.5rem 0 0 0; color:#047857;">すべてのチェック項目をパスしました</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.header("📊 校閲結果")

    # サマリカード
    st.subheader("サマリ")
    cols = st.columns(4)

    with cols[0]:
        fail_class = "summary-fail" if report.summary["Fail"] > 0 else "summary-ok"
        st.markdown(f"""
        <div class="summary-card {fail_class}">
            <p class="summary-number">{report.summary["Fail"]}</p>
            <p class="summary-label">❌ Fail（要修正）</p>
        </div>
        """, unsafe_allow_html=True)

    with cols[1]:
        warn_class = "summary-warning" if report.summary["Warning"] > 0 else "summary-ok"
        st.markdown(f"""
        <div class="summary-card {warn_class}">
            <p class="summary-number">{report.summary["Warning"]}</p>
            <p class="summary-label">⚠️ Warning（要確認）</p>
        </div>
        """, unsafe_allow_html=True)

    with cols[2]:
        st.markdown(f"""
        <div class="summary-card summary-info">
            <p class="summary-number">{report.summary["Info"]}</p>
            <p class="summary-label">ℹ️ Info（参考情報）</p>
        </div>
        """, unsafe_allow_html=True)

    with cols[3]:
        total = report.summary["Fail"] + report.summary["Warning"] + report.summary["Info"]
        st.markdown(f"""
        <div class="summary-card summary-ok">
            <p class="summary-number">{total}</p>
            <p class="summary-label">📋 合計チェック数</p>
        </div>
        """, unsafe_allow_html=True)

    # --- 指摘一覧（カード形式） ---
    st.subheader("指摘詳細")

    section_icons = {
        "ATM画像チェック": "🏧",
        "ロゴチェック": "🎨",
        "表記・ワーディングチェック": "📝",
        "形式チェック": "📋",
    }

    for section in report.sections:
        icon = section_icons.get(section.title, "📌")

        with st.expander(f"{icon} {section.title}", expanded=not section.is_na):
            if section.is_na:
                st.info("該当なし - このカテゴリのチェック対象はありませんでした")
            elif not section.issues:
                st.success("✅ 問題なし - このカテゴリで指摘事項はありませんでした")
            else:
                if section.reference:
                    st.caption(f"参照: {section.reference}")

                for issue in section.issues:
                    severity_lower = issue.severity.lower()
                    badge_class = f"badge-{severity_lower}"
                    card_class = f"issue-{severity_lower}"

                    emoji = {"fail": "❌", "warning": "⚠️", "info": "ℹ️"}.get(severity_lower, "📌")

                    st.markdown(f"""
                    <div class="issue-card {card_class}">
                        <div class="issue-header">
                            <span class="issue-badge {badge_class}">{issue.severity}</span>
                            <span style="color:#374151; font-weight:500;">#{issue.number}</span>
                        </div>
                        <div class="issue-content">
                            {emoji} {issue.content}
                        </div>
                        <div class="issue-meta">
                            <strong>根拠:</strong> {issue.basis} &nbsp;|&nbsp;
                            <strong>箇所:</strong> {issue.location} &nbsp;|&nbsp;
                            <strong>対応:</strong> {issue.action}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    # --- 目視確認リスト ---
    if report.visual_checks:
        st.subheader("👁️ 目視確認リスト")
        st.warning("以下の項目はAIによる自動判定に限界があります。担当者による確認をお願いします。")

        for check in report.visual_checks:
            st.markdown(f"""
            <div class="visual-check">
                ☐ {check}
            </div>
            """, unsafe_allow_html=True)

    # --- 備考 ---
    if report.notes:
        with st.expander("📝 備考", expanded=False):
            for note in report.notes:
                st.markdown(f"- {note}")

    # --- 生のMarkdown表示（オプション） ---
    if show_raw:
        with st.expander("📄 生のMarkdownレポート", expanded=False):
            st.markdown(result_text)

    # --- ダウンロード ---
    st.divider()
    col1, col2 = st.columns([3, 1])
    with col2:
        download_content = wrap_report(result_text, uploaded_file.name)
        download_filename = generate_filename(uploaded_file.name)
        st.download_button(
            label="📥 レポートをダウンロード",
            data=download_content,
            file_name=download_filename,
            mime="text/markdown",
            use_container_width=True,
        )
