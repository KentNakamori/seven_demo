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
from preset_manager import get_announcement_types, get_partners, get_additional_rules

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

/* カーソルスタイル */
button,
[role="button"],
.stButton > button,
.stDownloadButton > button,
.stSelectbox > div > div,
.stCheckbox > label,
.stRadio > label,
.stFileUploader > div,
[data-baseweb="select"],
[data-baseweb="popover"] li,
summary,
.streamlit-expanderHeader {
    cursor: pointer !important;
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

/* サマリカード - シンプル版 */
.summary-container {
    display: flex;
    gap: 2rem;
    margin: 1.5rem 0;
    padding: 1.5rem 0;
    border-bottom: 1px solid #e5e7eb;
}
.summary-item {
    text-align: center;
}
.summary-number {
    font-size: 2.5rem;
    font-weight: 700;
    margin: 0;
    line-height: 1;
}
.summary-number.fail { color: #dc2626; }
.summary-number.warning { color: #d97706; }
.summary-number.info { color: #6b7280; }
.summary-label {
    font-size: 0.8rem;
    color: #9ca3af;
    margin-top: 0.25rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* 指摘カード - シンプル版 */
.issue-card {
    padding: 1rem 0;
    border-bottom: 1px solid #f3f4f6;
}
.issue-card:last-child {
    border-bottom: none;
}
.issue-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
}
.issue-badge {
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
}
.badge-fail { background: #fee2e2; color: #dc2626; }
.badge-warning { background: #fef3c7; color: #d97706; }
.badge-info { background: #e0e7ff; color: #4f46e5; }
.issue-content {
    font-size: 0.95rem;
    color: #1f2937;
    margin-bottom: 0.5rem;
    line-height: 1.5;
}
.issue-meta {
    font-size: 0.8rem;
    color: #9ca3af;
}
.issue-meta span {
    margin-right: 1rem;
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

/* 目視確認 - シンプル版 */
.visual-check {
    padding: 0.75rem 0;
    color: #92400e;
    font-size: 0.9rem;
    border-bottom: 1px solid #fef3c7;
}
.visual-check:last-child {
    border-bottom: none;
}

/* 成功メッセージ - シンプル版 */
.success-box {
    text-align: center;
    padding: 3rem 2rem;
}
.success-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
}
.success-text {
    font-size: 1.25rem;
    color: #059669;
    font-weight: 600;
}
.success-sub {
    font-size: 0.9rem;
    color: #6b7280;
    margin-top: 0.5rem;
}

/* エラー */
.error-text {
    color: #dc2626;
    font-size: 0.9rem;
}

/* 実行ボタン */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: white;
    border: none;
    padding: 1rem 2.5rem;
    font-size: 1.1rem;
    font-weight: 700;
    border-radius: 12px;
    transition: all 0.2s ease;
    box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4);
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(239, 68, 68, 0.5);
    background: linear-gradient(135deg, #f87171 0%, #ef4444 100%);
}
.stButton > button[kind="primary"]:active {
    transform: translateY(0);
}
.stButton > button {
    border-radius: 10px;
    font-weight: 600;
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
    background: #f8fafc;
}
section[data-testid="stSidebar"] .stMarkdown {
    color: #334155;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #1e293b;
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

    # プリセット選択
    st.markdown("### 📋 告知物設定")
    preset_col1, preset_col2 = st.columns(2)

    # 告知物タイプ
    announcement_types = get_announcement_types()
    type_keys = list(announcement_types.keys())
    type_names = list(announcement_types.values())
    with preset_col1:
        selected_type_idx = st.selectbox(
            "告知物タイプ",
            range(len(type_keys)),
            format_func=lambda i: type_names[i],
            index=0,
        )
        selected_type = type_keys[selected_type_idx]

    # 提携先
    partners = get_partners()
    partner_keys = list(partners.keys())
    partner_names = list(partners.values())
    with preset_col2:
        selected_partner_idx = st.selectbox(
            "提携先",
            range(len(partner_keys)),
            format_func=lambda i: partner_names[i],
            index=0,
        )
        selected_partner = partner_keys[selected_partner_idx]

    # 追加ルール表示
    additional_rules = get_additional_rules(selected_type, selected_partner)
    if additional_rules:
        rules_text = "\n".join([f"・{rule}" for rule in additional_rules])
        st.info(f"**📋 適用される追加ルール:**\n{rules_text}")

with col_side:
    # チェック項目
    st.markdown("### ✅ チェック項目")
    chk_atm = st.checkbox("ATM画像（種類・禁則）", value=True)
    chk_logo = st.checkbox("ロゴ（形・色・余白）", value=True)
    chk_wording = st.checkbox("表記・ワーディング", value=True)
    chk_format = st.checkbox("形式（日付・金額）", value=True)
    st.markdown("#### 🎨 追加チェック")
    chk_color = st.checkbox("カラーUD（色覚配慮）", value=False)
    chk_improvement = st.checkbox("表現改善提案", value=False)

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
        "color": chk_color,
        "improvement": chk_improvement,
    }

    active_checks = sum(1 for v in check_items.values() if v)
    if active_checks == 0:
        st.warning("⚠️ 少なくとも1つのチェック項目を選択してください")
        st.stop()

    prompts = build_prompts_for_parallel(additional_rules=additional_rules)
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
        <div class="success-box">
            <div class="success-icon">✓</div>
            <div class="success-text">校閲完了 - 問題なし</div>
            <div class="success-sub">すべてのチェック項目をパスしました</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # サマリ
        st.markdown(f"""
        <div class="summary-container">
            <div class="summary-item">
                <div class="summary-number fail">{report.summary["Fail"]}</div>
                <div class="summary-label">Fail</div>
            </div>
            <div class="summary-item">
                <div class="summary-number warning">{report.summary["Warning"]}</div>
                <div class="summary-label">Warning</div>
            </div>
            <div class="summary-item">
                <div class="summary-number info">{report.summary["Info"]}</div>
                <div class="summary-label">Info</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # --- 指摘一覧 ---
    section_icons = {"atm": "🏧", "logo": "🎨", "wording": "📝", "format": "📋", "color": "🌈", "improvement": "💡"}

    for section in report.sections:
        icon = section_icons.get(section.category, "📌")
        has_issues = len(section.issues) > 0 or section.error is not None

        with st.expander(f"{icon} {section.title}", expanded=has_issues):
            if section.error:
                st.markdown(f'<div class="error-text">⚠️ {section.error}</div>', unsafe_allow_html=True)
            elif not section.has_target:
                st.caption("該当なし")
            elif not section.issues:
                st.caption("✓ 問題なし")
            else:
                for issue in section.issues:
                    sev = issue.severity.lower()
                    st.markdown(f"""
                    <div class="issue-card">
                        <div class="issue-header">
                            <span class="issue-badge badge-{sev}">{issue.severity}</span>
                        </div>
                        <div class="issue-content">{issue.content}</div>
                        <div class="issue-meta">
                            <span>根拠: {issue.basis}</span>
                            <span>箇所: {issue.location}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    # --- 目視確認リスト ---
    if report.visual_checks:
        st.markdown("### 👁️ 目視確認が必要な項目")
        for check in report.visual_checks:
            st.markdown(f'<div class="visual-check">☐ {check}</div>', unsafe_allow_html=True)

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
    st.markdown("")
    download_content = generate_markdown_report(report, uploaded_file.name)
    download_filename = generate_filename(uploaded_file.name)
    st.download_button(
        label="📥 レポートをダウンロード",
        data=download_content,
        file_name=download_filename,
        mime="text/markdown",
    )
