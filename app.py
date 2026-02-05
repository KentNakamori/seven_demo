"""
セブン銀行 AI校閲支援ツール（デモ版）- 分割並列処理版

Streamlit アプリ本体。
ファイルアップロード → Gemini API で並列校閲 → レポート表示。
"""

import streamlit as st
from PIL import Image
from dotenv import load_dotenv

from api_client import configure_api, run_proofread_parallel, CHECK_CONFIGS
from prompt_builder import build_prompts_for_parallel
from report_generator import merge_results, generate_markdown_report, generate_filename

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

/* エラーカード */
.error-card {
    padding: 1rem 1.5rem;
    border-radius: 8px;
    margin-bottom: 0.75rem;
    background-color: #fef2f2;
    border-left: 4px solid #ef4444;
}

/* 進捗表示 */
.progress-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0;
}
</style>
""", unsafe_allow_html=True)

# --- サイドバー ---
with st.sidebar:
    st.header("⚙ 設定")

    st.subheader("チェックカテゴリ")
    for cat, config in CHECK_CONFIGS.items():
        ref_count = len(config["files"])
        st.text(f"・{config['name']}（参照画像{ref_count}枚）")

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
    show_raw = st.checkbox("生のJSONレスポンスも表示", value=False)

# --- メインエリア ---
st.title("📋 セブン銀行 AI校閲支援ツール（デモ）")

st.caption("🚀 分割並列処理版 - 各チェックカテゴリを個別に実行して精度向上")

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

    check_items = {
        "atm": chk_atm,
        "logo": chk_logo,
        "wording": chk_wording,
        "format": chk_format,
    }

    # 有効なチェック数をカウント
    active_checks = sum(1 for v in check_items.values() if v)
    if active_checks == 0:
        st.warning("⚠️ 少なくとも1つのチェック項目を選択してください")
        st.stop()

    # プロンプト生成
    prompts = build_prompts_for_parallel()
    image = Image.open(uploaded_file)

    # 進捗表示
    progress_placeholder = st.empty()
    with progress_placeholder.container():
        st.info(f"🔍 校閲を実行中... {active_checks}カテゴリを並列処理しています")
        progress_bar = st.progress(0)

    try:
        # 並列処理実行
        check_results = run_proofread_parallel(
            target_image=image,
            prompts=prompts,
            model_name=model_name,
            check_items=check_items,
        )
        progress_bar.progress(100)
    except Exception as e:
        st.error(f"❌ API呼び出しエラー: {e}")
        st.stop()

    # 進捗表示をクリア
    progress_placeholder.empty()

    # 結果をマージ
    report = merge_results(check_results)

    # --- 結果表示 ---
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
        "atm": "🏧",
        "logo": "🎨",
        "wording": "📝",
        "format": "📋",
    }

    for section in report.sections:
        icon = section_icons.get(section.category, "📌")

        # セクションに問題があるか判定
        has_issues = len(section.issues) > 0 or section.error is not None

        with st.expander(f"{icon} {section.title}", expanded=has_issues):
            if section.error:
                st.markdown(f"""
                <div class="error-card">
                    ⚠️ <strong>エラー:</strong> {section.error}
                </div>
                """, unsafe_allow_html=True)
            elif not section.has_target:
                st.info("該当なし - このカテゴリのチェック対象はありませんでした")
            elif not section.issues:
                st.success("✅ 問題なし - このカテゴリで指摘事項はありませんでした")
            else:
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

    # --- 生のJSONレスポンス表示（オプション） ---
    if show_raw:
        with st.expander("📄 生のAPIレスポンス（デバッグ用）", expanded=False):
            for result in report.raw_results:
                st.markdown(f"### {result.name}")
                if result.success:
                    st.code(result.result_text, language="json")
                else:
                    st.error(f"エラー: {result.error}")

    # --- ダウンロード ---
    st.divider()
    col1, col2 = st.columns([3, 1])
    with col2:
        download_content = generate_markdown_report(report, uploaded_file.name)
        download_filename = generate_filename(uploaded_file.name)
        st.download_button(
            label="📥 レポートをダウンロード",
            data=download_content,
            file_name=download_filename,
            mime="text/markdown",
            use_container_width=True,
        )
