"""
レポート生成モジュール

APIレスポンス（Markdown文字列）をパースし、
UI表示用の構造化データに変換する。
"""

import re
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class Issue:
    """個別の指摘事項"""
    number: int
    severity: str  # Fail / Warning / Info
    content: str
    basis: str  # 根拠
    location: str  # 該当箇所
    action: str  # 次アクション


@dataclass
class CheckSection:
    """チェックカテゴリごとのセクション"""
    title: str
    reference: str
    issues: list[Issue] = field(default_factory=list)
    is_na: bool = False  # 該当なしフラグ


@dataclass
class ParsedReport:
    """パース済みレポート"""
    summary: dict[str, int]
    sections: list[CheckSection]
    visual_checks: list[str]  # 目視確認リスト
    notes: list[str]  # 備考
    raw_text: str  # 元のMarkdown


def extract_summary(report_text: str) -> dict[str, int]:
    """
    レポートテキストからサマリ行（Fail/Warning/Info件数）を抽出する。
    """
    counts = {"Fail": 0, "Warning": 0, "Info": 0}

    # サマリテーブルからの抽出を試みる
    table_match = re.search(
        r"\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|",
        report_text,
    )
    if table_match:
        counts["Fail"] = int(table_match.group(1))
        counts["Warning"] = int(table_match.group(2))
        counts["Info"] = int(table_match.group(3))
        return counts

    # フォールバック: テキスト内の重大度ラベルをカウント
    counts["Fail"] = len(re.findall(r"\bFail\b", report_text))
    counts["Warning"] = len(re.findall(r"\bWarning\b", report_text))
    counts["Info"] = len(re.findall(r"\bInfo\b", report_text))
    return counts


def _parse_issues_from_table(table_text: str) -> list[Issue]:
    """テーブル形式の指摘一覧をパースする"""
    issues = []
    # テーブル行を抽出（ヘッダーとセパレータを除く）
    rows = re.findall(
        r"\|\s*(\d+)\s*\|\s*(\w+)\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|",
        table_text
    )
    for row in rows:
        try:
            issues.append(Issue(
                number=int(row[0]),
                severity=row[1].strip(),
                content=row[2].strip(),
                basis=row[3].strip(),
                location=row[4].strip(),
                action=row[5].strip(),
            ))
        except (ValueError, IndexError):
            continue
    return issues


def _extract_section(text: str, section_name: str) -> tuple[str, str, list[Issue], bool]:
    """セクションを抽出してパースする"""
    # セクション開始を探す
    pattern = rf"###\s*{re.escape(section_name)}.*?(?=###|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)

    if not match:
        return section_name, "", [], True

    section_text = match.group(0)

    # 該当なしチェック
    if "該当なし" in section_text or "なし" in section_text.split("\n")[0]:
        return section_name, "", [], True

    # 参照を抽出
    ref_match = re.search(r"参照[:：]\s*(.+?)(?:\n|$)", section_text)
    reference = ref_match.group(1).strip() if ref_match else ""

    # テーブルから指摘を抽出
    issues = _parse_issues_from_table(section_text)

    return section_name, reference, issues, False


def _extract_visual_checks(text: str) -> list[str]:
    """目視確認リストを抽出する"""
    checks = []
    # 目視確認リストセクションを探す
    match = re.search(r"##\s*目視確認リスト.*?(?=##|\Z)", text, re.DOTALL)
    if match:
        section = match.group(0)
        # チェックボックス形式の項目を抽出
        items = re.findall(r"-\s*\[.\]\s*(.+?)(?:\n|$)", section)
        checks = [item.strip() for item in items if item.strip()]
    return checks


def _extract_notes(text: str) -> list[str]:
    """備考を抽出する"""
    notes = []
    match = re.search(r"##\s*備考.*?(?=##|\Z)", text, re.DOTALL)
    if match:
        section = match.group(0)
        items = re.findall(r"-\s*(.+?)(?:\n|$)", section)
        notes = [item.strip() for item in items if item.strip() and not item.startswith("[")]
    return notes


def parse_report(report_text: str) -> ParsedReport:
    """
    レポートテキストをパースして構造化データに変換する。
    """
    summary = extract_summary(report_text)

    sections = []
    section_configs = [
        ("ATM画像チェック", "ATM画像"),
        ("ロゴチェック", "ロゴ"),
        ("表記・ワーディングチェック", "表記"),
        ("形式チェック", "形式"),
    ]

    for title, _ in section_configs:
        name, ref, issues, is_na = _extract_section(report_text, title)
        sections.append(CheckSection(
            title=name,
            reference=ref,
            issues=issues,
            is_na=is_na,
        ))

    visual_checks = _extract_visual_checks(report_text)
    notes = _extract_notes(report_text)

    return ParsedReport(
        summary=summary,
        sections=sections,
        visual_checks=visual_checks,
        notes=notes,
        raw_text=report_text,
    )


def wrap_report(
    report_text: str,
    input_filename: str,
) -> str:
    """
    APIレスポンスに実行情報ヘッダを付加してダウンロード用レポートを生成する。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"""<!-- 自動生成レポート -->
<!-- 実行日時: {now} -->
<!-- 入力ファイル: {input_filename} -->

"""
    return header + report_text


def generate_filename(input_filename: str) -> str:
    """ダウンロード用ファイル名を生成する。"""
    stem = re.sub(r"\.[^.]+$", "", input_filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"report_{stem}_{timestamp}.md"
