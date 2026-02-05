"""
レポート生成モジュール（分割並列処理版）

並列処理の結果（JSON形式）をパースし、
UI表示用の構造化データに変換・統合する。
"""

import json
import re
from datetime import datetime
from dataclasses import dataclass, field

from api_client import CheckResult


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
    category: str
    issues: list[Issue] = field(default_factory=list)
    visual_checks: list[str] = field(default_factory=list)
    has_target: bool = True
    error: str | None = None


@dataclass
class ParsedReport:
    """パース済みレポート"""
    summary: dict[str, int]
    sections: list[CheckSection]
    visual_checks: list[str]  # 全カテゴリ統合の目視確認リスト
    raw_results: list[CheckResult]  # 元の結果


def _parse_json_result(result_text: str) -> dict | None:
    """
    APIレスポンスからJSONを抽出してパースする。
    """
    # マークダウンコードブロックからJSONを抽出
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", result_text)
    if json_match:
        json_str = json_match.group(1)
    else:
        # コードブロックがない場合は全体をJSONとして試す
        json_str = result_text.strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def _parse_single_result(check_result: CheckResult) -> CheckSection:
    """
    単一カテゴリの CheckResult を CheckSection に変換する。
    """
    if not check_result.success:
        return CheckSection(
            title=check_result.name,
            category=check_result.category,
            issues=[],
            visual_checks=[],
            has_target=False,
            error=check_result.error,
        )

    parsed = _parse_json_result(check_result.result_text)

    if parsed is None:
        # JSONパース失敗 - テキストをそのままエラーとして扱う
        return CheckSection(
            title=check_result.name,
            category=check_result.category,
            issues=[],
            visual_checks=[],
            has_target=True,
            error=f"JSONパースエラー: {check_result.result_text[:200]}...",
        )

    # issuesをパース
    issues = []
    for i, issue_data in enumerate(parsed.get("issues", []), 1):
        issues.append(Issue(
            number=issue_data.get("number", i),
            severity=issue_data.get("severity", "Info"),
            content=issue_data.get("content", ""),
            basis=issue_data.get("basis", ""),
            location=issue_data.get("location", ""),
            action=issue_data.get("action", ""),
        ))

    return CheckSection(
        title=check_result.name,
        category=check_result.category,
        issues=issues,
        visual_checks=parsed.get("visual_checks", []),
        has_target=parsed.get("has_target", True),
        error=None,
    )


def merge_results(check_results: list[CheckResult]) -> ParsedReport:
    """
    並列処理の結果リストを統合してレポートを生成する。
    """
    sections = []
    all_visual_checks = []
    summary = {"Fail": 0, "Warning": 0, "Info": 0}

    # カテゴリ順にソート
    category_order = ["atm", "logo", "wording", "format"]
    sorted_results = sorted(
        check_results,
        key=lambda r: category_order.index(r.category) if r.category in category_order else 99
    )

    for result in sorted_results:
        section = _parse_single_result(result)
        sections.append(section)

        # 目視確認リストを統合
        all_visual_checks.extend(section.visual_checks)

        # サマリカウント
        for issue in section.issues:
            sev = issue.severity
            if sev in summary:
                summary[sev] += 1

    return ParsedReport(
        summary=summary,
        sections=sections,
        visual_checks=all_visual_checks,
        raw_results=check_results,
    )


def generate_markdown_report(parsed_report: ParsedReport, input_filename: str) -> str:
    """
    ParsedReport から Markdown レポートを生成する（ダウンロード用）。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# セブン銀行 AI校閲レポート",
        f"",
        f"- 実行日時: {now}",
        f"- 入力ファイル: {input_filename}",
        f"",
        f"## サマリ",
        f"",
        f"| Fail | Warning | Info |",
        f"|------|---------|------|",
        f"| {parsed_report.summary['Fail']} | {parsed_report.summary['Warning']} | {parsed_report.summary['Info']} |",
        f"",
    ]

    for section in parsed_report.sections:
        lines.append(f"## {section.title}")
        lines.append("")

        if section.error:
            lines.append(f"> ⚠️ エラー: {section.error}")
            lines.append("")
            continue

        if not section.has_target:
            lines.append("該当なし")
            lines.append("")
            continue

        if not section.issues:
            lines.append("✅ 問題なし")
            lines.append("")
            continue

        lines.append("| No | 重大度 | 指摘内容 | 根拠 | 該当箇所 | 対応 |")
        lines.append("|-----|--------|----------|------|----------|------|")

        for issue in section.issues:
            lines.append(
                f"| {issue.number} | {issue.severity} | {issue.content} | "
                f"{issue.basis} | {issue.location} | {issue.action} |"
            )
        lines.append("")

    if parsed_report.visual_checks:
        lines.append("## 目視確認リスト")
        lines.append("")
        for check in parsed_report.visual_checks:
            lines.append(f"- [ ] {check}")
        lines.append("")

    return "\n".join(lines)


def generate_filename(input_filename: str) -> str:
    """ダウンロード用ファイル名を生成する。"""
    stem = re.sub(r"\.[^.]+$", "", input_filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"report_{stem}_{timestamp}.md"


# ============================================================
# 後方互換性のための旧関数
# ============================================================

def extract_summary(report_text: str) -> dict[str, int]:
    """
    【非推奨】レポートテキストからサマリ行を抽出する。
    """
    counts = {"Fail": 0, "Warning": 0, "Info": 0}

    table_match = re.search(
        r"\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|",
        report_text,
    )
    if table_match:
        counts["Fail"] = int(table_match.group(1))
        counts["Warning"] = int(table_match.group(2))
        counts["Info"] = int(table_match.group(3))
        return counts

    counts["Fail"] = len(re.findall(r"\bFail\b", report_text))
    counts["Warning"] = len(re.findall(r"\bWarning\b", report_text))
    counts["Info"] = len(re.findall(r"\bInfo\b", report_text))
    return counts


@dataclass
class OldParsedReport:
    """【非推奨】旧パース済みレポート"""
    summary: dict[str, int]
    sections: list
    visual_checks: list[str]
    notes: list[str]
    raw_text: str


def parse_report(report_text: str) -> OldParsedReport:
    """
    【非推奨】旧Markdown形式のレポートをパースする。
    """
    summary = extract_summary(report_text)
    return OldParsedReport(
        summary=summary,
        sections=[],
        visual_checks=[],
        notes=[],
        raw_text=report_text,
    )


def wrap_report(report_text: str, input_filename: str) -> str:
    """
    【非推奨】APIレスポンスに実行情報ヘッダを付加する。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"""<!-- 自動生成レポート -->
<!-- 実行日時: {now} -->
<!-- 入力ファイル: {input_filename} -->

"""
    return header + report_text
