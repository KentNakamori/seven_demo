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
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- カスタムCSS ---
st.markdown("""
<style>
/* フォント */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap');

* {
    font-family: 'Noto Sans JP', sans-serif;
}

/* メインコンテナ */
.main .block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 1200px;
}

/* ヘッダー */
.main-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
    padding: 2rem 2.5rem;
    border-radius: 16px;
    margin-bottom: 2rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}
.main-header h1 {
    color: white;
    font-size: 2rem;
    font-weight: 700;
    margin: 0 0 0.5rem 0;
}
.main-header p {
    color: rgba(255,255,255,0.85);
    font-size: 1rem;
    margin: 0;
}
.header-badge {
    display: inline-block;
    background: rgba(255,255,255,0.2);
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-size: 0.8rem;
    margin-top: 0.75rem;
}

/* アップロードエリア */
.upload-section {
    background: #f8fafc;
    border: 2px dashed #cbd5e1;
    border-radius: 16px;
    padding: 2rem;
    text-align: center;
    transition: all 0.3s ease;
}
.upload-section:hover {
    border-color: #3b82f6;
    background: #f1f5f9;
}

/* チェック項目カード */
.check-options {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1.5rem;
    margin: 1rem 0;
}
.check-options h3 {
    color: #1e293b;
    font-size: 1rem;
    font-weight: 600;
    margin-bottom: 1rem;
}

/* サマリカード */
.summary-container {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin: 1.5rem 0;
}
.summary-card {
    padding: 1.5rem;
    border-radius: 16px;
    text-align: center;
    transition: transform 0.2s ease;
}
.summary-card:hover {
    transform: translateY(-2px);
}
.summary-fail {
    background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
    border: 1px solid #fecaca;
}
.summary-warning {
    background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
    border: 1px solid #fde68a;
}
.summary-info {
    background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    border: 1px solid #bfdbfe;
}
.summary-ok {
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    border: 1px solid #bbf7d0;
}
.summary-number {
    font-size: 2.5rem;
    font-weight: 700;
    margin: 0;
    line-height: 1;
}
.summary-fail .summary-number { color: #dc2626; }
.summary-warning .summary-number { color: #d97706; }
.summary-info .summary-number { color: #2563eb; }
.summary-ok .summary-number { color: #16a34a; }
.summary-label {
    font-size: 0.85rem;
    color: #64748b;
    margin-top: 0.5rem;
    font-weight: 500;
}

/* 指摘カード */
.issue-card {
    background: white;
    padding: 1.25rem 1.5rem;
    border-radius: 12px;
    margin-bottom: 0.75rem;
    border-left: 4px solid;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    transition: box-shadow 0.2s ease;
}
.issue-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.issue-fail {
    border-left-color: #ef4444;
    background: linear-gradient(to right, #fef2f2, white);
}
.issue-warning {
    border-left-color: #f59e0b;
    background: linear-gradient(to right, #fffbeb, white);
}
.issue-info {
    border-left-color: #3b82f6;
    background: linear-gradient(to right, #eff6ff, white);
}
.issue-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
}
.issue-badge {
    padding: 0.3rem 0.8rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    color: white;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.badge-fail { background: linear-gradient(135deg, #ef4444, #dc2626); }
.badge-warning { background: linear-gradient(135deg, #f59e0b, #d97706); }
.badge-info { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.issue-content {
    font-size: 1rem;
    color: #1e293b;
    margin-bottom: 0.75rem;
    font-weight: 500;
}
.issue-meta {
    font-size: 0.85rem;
    color: #64748b;
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
}
.issue-meta-item {
    display: flex;
    align-items: center;
    gap: 0.25rem;
}
.issue-meta-label {
    color: #94a3b8;
}

/* セクションヘッダー */
.section-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 1rem 1.25rem;
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    border-radius: 12px;
    margin-bottom: 1rem;
    border: 1px solid #e2e8f0;
}
.section-icon {
    font-size: 1.5rem;
}
.section-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #1e293b;
    margin: 0;
}

/* 目視確認 */
.visual-check {
    padding: 1rem 1.25rem;
    background: linear-gradient(135deg, #fefce8 0%, #fef9c3 100%);
    border: 1px solid #fde047;
    border-radius: 10px;
    margin-bottom: 0.5rem;
    color: #854d0e;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.visual-check-icon {
    font-size: 1.2rem;
}

/* 成功メッセージ */
.success-message {
    padding: 2rem;
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    border: 2px solid #86efac;
    border-radius: 16px;
    text-align: center;
}
.success-message h2 {
    color: #166534;
    font-size: 1.5rem;
    margin: 0 0 0.5rem 0;
}
.success-message p {
    color: #15803d;
    margin: 0;
}

/* エラーカード */
.error-card {
    padding: 1rem 1.5rem;
    border-radius: 12px;
    background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
    border: 1px solid #fecaca;
    color: #991b1b;
}

/* ボタン */
.stButton > button {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
    border: none;
    padding: 0.75rem 2rem;
    font-size: 1rem;
    font-weight: 600;
    border-radius: 10px;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}
.stButton > button:active {
    transform: translateY(0);
}

/* ダウンロードボタン */
.stDownloadButton > button {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    color: white;
    border: none;
    border-radius: 10px;
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
}

/* Expander */
.streamlit-expanderHeader {
    background: #f8fafc;
    border-radius: 10px;
    font-weight: 600;
}

/* サイドバー */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
}
section[data-testid="stSidebar"] .stMarkdown {
    color: #e2e8f0;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: white;
}

/* プログレス */
.stProgress > div > div {
    background: linear-gradient(90deg, #3b82f6, #8b5cf6);
}

/* ファイルアップローダー */
.stFileUploader > div {
    border-radius: 12px;
}

/* 結果セクション */
.results-section {
    background: white;
    border-radius: 16px;
    padding: 1.5rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    border: 1px solid #e2e8f0;
    margin-top: 1.5rem;
}
</style>
""", unsafe_allow_html=True)

# --- ヘッダー ---
st.markdown("""
<div class="main-header">
    <h1>🏦 セブン銀行 AI校閲支援ツール</h1>
    <p>告知物（ポスター・チラシ・バナー等）をAIが自動で校閲し、VIマニュアル違反をチェックします</p>
    <span class="header-badge">✨ Powered by Gemini 2.5 Pro</span>
</div>
""", unsafe_allow_html=True)

# --- サイドバー ---
with st.sidebar:
    st.markdown("### ⚙️ 設定")

    model_name = st.selectbox(
        "AIモデル",
        ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"],
        index=0,
        help="2.5-pro（推奨）は高精度。Flash系は高速だが精度が低い。"
    )

    st.divider()

    st.markdown("### 📋 チェックカテゴリ")
    for cat, config in CHECK_CONFIGS.items():
        ref_count = len(config["files"])
        if ref_count > 0:
            st.markdown(f"- {config['name']}（参照画像{ref_count}枚）")
        else:
            st.markdown(f"- {config['name']}")

    st.divider()

    show_raw = st.checkbox("デバッグ情報を表示", value=False)

# --- メインエリア ---
col_main, col_side = st.columns([2, 1])

with col_main:
    # ファイルアップロード
    st.markdown("### 📤 チェック対象ファイル")
    uploaded_file = st.file_uploader(
        "PNG / JPG 形式の告知物画像をアップロード",
        type=["png", "jpg", "jpeg"],
        label_visibility="collapsed",
    )

with col_side:
    # チェック項目
    st.markdown("### ✅ チェック項目")
    chk_atm = st.checkbox("ATM画像（種類・禁則）", value=True)
    chk_logo = st.checkbox("ロゴ（形・色・余白）", value=True)
    chk_wording = st.checkbox("表記・ワーディング", value=True)
    chk_format = st.checkbox("形式（日付・金額）", value=True)

# アップロード画像のプレビュー
if uploaded_file is not None:
    image = Image.open(uploaded_file)
    with st.expander("🖼️ アップロード画像プレビュー", expanded=False):
        st.image(image, use_container_width=True)

# --- 校閲実行 ---
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    run_button = st.button(
        "🔍 校閲を実行",
        type="primary",
        disabled=uploaded_file is None,
        use_container_width=True,
    )

if run_button:
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

    active_checks = sum(1 for v in check_items.values() if v)
    if active_checks == 0:
        st.warning("⚠️ 少なくとも1つのチェック項目を選択してください")
        st.stop()

    prompts = build_prompts_for_parallel()
    image = Image.open(uploaded_file)

    # 進捗表示
    progress_container = st.container()
    with progress_container:
        st.info(f"🔍 校閲を実行中... {active_checks}カテゴリを並列処理しています")
        progress_bar = st.progress(0)

    try:
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
    progress_container.empty()

    # 結果をマージ
    report = merge_results(check_results)

    # --- 結果表示 ---
    st.markdown("---")

    # 結果ヘッダー
    total_issues = report.summary["Fail"] + report.summary["Warning"]
    if total_issues == 0:
        st.markdown("""
        <div class="success-message">
            <h2>✅ 校閲完了</h2>
            <p>問題は見つかりませんでした。すべてのチェック項目をパスしました。</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("## 📊 校閲結果")

    # サマリカード
    st.markdown(f"""
    <div class="summary-container">
        <div class="summary-card {"summary-fail" if report.summary["Fail"] > 0 else "summary-ok"}">
            <p class="summary-number">{report.summary["Fail"]}</p>
            <p class="summary-label">❌ Fail（要修正）</p>
        </div>
        <div class="summary-card {"summary-warning" if report.summary["Warning"] > 0 else "summary-ok"}">
            <p class="summary-number">{report.summary["Warning"]}</p>
            <p class="summary-label">⚠️ Warning（要確認）</p>
        </div>
        <div class="summary-card summary-info">
            <p class="summary-number">{report.summary["Info"]}</p>
            <p class="summary-label">ℹ️ Info（参考）</p>
        </div>
        <div class="summary-card summary-ok">
            <p class="summary-number">{report.summary["Fail"] + report.summary["Warning"] + report.summary["Info"]}</p>
            <p class="summary-label">📋 合計</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- 指摘一覧 ---
    st.markdown("### 📝 指摘詳細")

    section_icons = {
        "atm": "🏧",
        "logo": "🎨",
        "wording": "📝",
        "format": "📋",
    }

    for section in report.sections:
        icon = section_icons.get(section.category, "📌")
        has_issues = len(section.issues) > 0 or section.error is not None

        with st.expander(f"{icon} {section.title}", expanded=has_issues):
            if section.error:
                st.markdown(f"""
                <div class="error-card">
                    ⚠️ <strong>エラー:</strong> {section.error}
                </div>
                """, unsafe_allow_html=True)
            elif not section.has_target:
                st.info("📭 該当なし - このカテゴリのチェック対象はありませんでした")
            elif not section.issues:
                st.success("✅ 問題なし - このカテゴリで指摘事項はありませんでした")
            else:
                for issue in section.issues:
                    severity_lower = issue.severity.lower()
                    badge_class = f"badge-{severity_lower}"
                    card_class = f"issue-{severity_lower}"

                    st.markdown(f"""
                    <div class="issue-card {card_class}">
                        <div class="issue-header">
                            <span class="issue-badge {badge_class}">{issue.severity}</span>
                        </div>
                        <div class="issue-content">{issue.content}</div>
                        <div class="issue-meta">
                            <span class="issue-meta-item"><span class="issue-meta-label">根拠:</span> {issue.basis}</span>
                            <span class="issue-meta-item"><span class="issue-meta-label">箇所:</span> {issue.location}</span>
                            <span class="issue-meta-item"><span class="issue-meta-label">対応:</span> {issue.action}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    # --- 目視確認リスト ---
    if report.visual_checks:
        st.markdown("### 👁️ 目視確認リスト")
        st.caption("以下の項目はAIによる自動判定に限界があります。担当者による確認をお願いします。")

        for check in report.visual_checks:
            st.markdown(f"""
            <div class="visual-check">
                <span class="visual-check-icon">☐</span>
                <span>{check}</span>
            </div>
            """, unsafe_allow_html=True)

    # --- デバッグ情報 ---
    if show_raw:
        with st.expander("🔧 デバッグ情報（APIレスポンス）", expanded=False):
            for result in report.raw_results:
                st.markdown(f"**{result.name}**")
                if result.success:
                    st.code(result.result_text, language="json")
                else:
                    st.error(f"エラー: {result.error}")

    # --- ダウンロード ---
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
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
