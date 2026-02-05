"""
プロンプト組み立てモジュール（分割処理版）

チェックカテゴリごとに専用のプロンプトを生成する。
"""

import yaml
from pathlib import Path

RULES_PATH = Path(__file__).parent / "rules" / "rules.yaml"

# 後方互換性のために残す
REFERENCE_CAPTIONS = [
    "参照画像1（ATM画像の種類ルール）：",
    "参照画像2（ATM画像の禁則事項）：",
    "参照画像3（ロゴの形・色の規定）：",
    "参照画像4（ロゴのアイソレーション・最小サイズ規定）：",
    "参照画像5（表記ルール表）：",
]


def load_rules() -> dict:
    """rules.yaml を読み込んで辞書として返す。"""
    if not RULES_PATH.exists():
        return {}
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _format_wording_rules(rules: list) -> str:
    """wording セクションのルールをプロンプト用テキストに変換。"""
    lines = []
    for r in rules:
        if r.get("type") == "banned_word":
            lines.append(
                f"- [{r['id']}] 禁止語「{r['pattern']}」→ {r['message']}（{r['severity']}）"
            )
        elif r.get("type") == "preferred_word":
            lines.append(
                f"- [{r['id']}] 表記ゆれ「{r['wrong']}」→「{r['correct']}」: {r['message']}（{r['severity']}）"
            )
    return "\n".join(lines)


def _format_format_rules(rules: list) -> str:
    """format セクションのルールをプロンプト用テキストに変換。"""
    lines = []
    for r in rules:
        note = f"（適用条件: {r['note']}）" if r.get("note") else ""
        lines.append(
            f"- [{r['id']}] {r['message']}{note}（{r['severity']}）"
        )
    return "\n".join(lines)


# ============================================================
# 分割プロンプト生成（カテゴリ別）
# ============================================================

def _build_common_prefix() -> str:
    """共通の前提ルール"""
    return """あなたはセブン銀行の告知物を校閲するAIアシスタントです。

## 前提ルール（最重要）
- **チェック対象画像に実際に存在する要素のみを指摘すること**
- 画像内に存在しない要素を「ある」と誤認して指摘してはいけない
- 指摘する際は、必ず「該当箇所」に画像内で実際に確認できた具体的な内容を記載すること
- 判定に自信がない場合は「要目視確認」とし、誤って「問題なし」としないこと
- 該当する要素がない場合は「該当なし」と記載すること
"""


def _build_output_format(category_name: str) -> str:
    """出力フォーマット指定"""
    return f"""
## 出力フォーマット
以下のJSON形式で出力してください。Markdown等の装飾は不要です。

```json
{{
  "category": "{category_name}",
  "issues": [
    {{
      "number": 1,
      "severity": "Fail または Warning または Info",
      "content": "指摘内容",
      "basis": "根拠（参照画像名 or ルールID）",
      "location": "該当箇所（画像内で確認できた具体的な位置や文言）",
      "action": "修正必須 または 要目視確認 または 問題なし"
    }}
  ],
  "visual_checks": ["目視確認が必要な項目1", "目視確認が必要な項目2"],
  "has_target": true
}}
```

- issuesが空の場合は空配列 `[]` を返す
- has_target: チェック対象（ATM画像/ロゴ/テキスト等）が画像内にあるか
- 対象がない場合は has_target: false とし、issuesは空配列
"""


def build_atm_prompt() -> str:
    """ATM画像チェック用プロンプト"""
    return _build_common_prefix() + """
## タスク: ATM画像チェック

チェック対象画像に含まれるATM画像（ATM筐体の写真やイラスト）を確認してください。

### 参照画像の説明
- 参照画像1（ATM画像の種類ルール）: ATM画像の5つの種類が示されている
  - ①正面（最推奨）
  - ②斜め（推奨）
  - ③正面イラスト
  - ④斜め・横イラスト
  - ⑤パーツイラスト
  - **原則、①正面か②斜めを使用する**

- 参照画像2（ATM画像の禁則事項）: 以下が禁止されている
  - ①縦横比の変更・変形
  - ②正体以外の配置、規定以外の向き（横にする、斜めに傾ける）
  - ③異なるテイストの併用
  - ④色の変更、一部の削除

### チェック手順
1. チェック対象画像にATM画像（筐体の写真やイラスト）が含まれるか確認
2. 含まれる場合、参照画像1と見比べて①〜⑤のどれに該当するか判定
3. ③〜⑤が使われている場合はWarning（デザイン上の意図を確認が必要）
4. 参照画像2の禁則と見比べ、変形・回転・色変更・一部削除がないか確認
5. 明らかな違反は Fail、微妙な場合は Warning
""" + _build_output_format("ATM画像チェック")


def build_logo_prompt() -> str:
    """ロゴチェック用プロンプト"""
    return _build_common_prefix() + """
## タスク: ロゴチェック

チェック対象画像に含まれるセブン銀行ロゴを確認してください。

### 参照画像の説明
- 参照画像1（ロゴの形・色の規定）:
  - シンボルマークとロゴタイプの組み合わせパターン
  - 使用できる色はコーポレートカラー（レッド、グリーン、オレンジ）または墨・白

- 参照画像2（アイソレーション・最小サイズ規定）:
  - ロゴ周囲に確保すべき余白（アイソレーション）
  - ロゴの最小使用サイズ

### チェック手順
1. チェック対象画像にセブン銀行ロゴが含まれるか確認
2. 含まれる場合、参照画像1と見比べてロゴの形・色が正規か確認
3. ロゴが極端に小さく使用されていないか確認

### 判定基準
- **ロゴの形・色の違反** → 明らかな違反は Fail、微妙な場合は Warning
- **アイソレーション（余白）** → **緩めに判定**。明らかに要素がロゴに重なっている場合のみ Warning。Fail はほぼ出さない
- **最小サイズ** → 極端に小さい場合のみ Warning
""" + _build_output_format("ロゴチェック")


def build_wording_prompt() -> str:
    """表記・ワーディングチェック用プロンプト"""
    rules = load_rules()
    wording_rules = rules.get("wording", [])

    prompt = _build_common_prefix() + """
## タスク: 表記・ワーディングチェック

チェック対象画像内のテキストを読み取り、表記ルールに違反がないか確認してください。
このチェックには参照画像はありません。以下のルールに基づいて判定してください。

### チェック手順
1. **まずチェック対象画像内のテキストを正確に読み取る**
2. 読み取ったテキストの中に、以下のルールに該当する語句があるか確認
3. **画像内に存在しない語句を指摘してはいけない**
"""

    if wording_rules:
        prompt += "\n### 表記ルール\n"
        prompt += _format_wording_rules(wording_rules)

    prompt += _build_output_format("表記・ワーディングチェック")
    return prompt


def build_format_prompt() -> str:
    """形式チェック用プロンプト"""
    rules = load_rules()
    format_rules = rules.get("format", [])

    prompt = _build_common_prefix() + """
## タスク: 形式チェック

チェック対象画像内のテキストを読み取り、形式ルールに従っているか確認してください。
このチェックには参照画像はありません。以下のルールに基づいて判定してください。

### チェック手順
1. チェック対象画像内のテキストを読み取る
2. 以下のフォーマットルールに照らし合わせる
3. **画像内に存在しないものは指摘しない**
"""

    if format_rules:
        prompt += "\n### フォーマットルール\n"
        prompt += _format_format_rules(format_rules)

    prompt += _build_output_format("形式チェック")
    return prompt


def build_prompts_for_parallel() -> dict[str, str]:
    """
    並列処理用に、カテゴリごとのプロンプトを辞書で返す。
    """
    return {
        "atm": build_atm_prompt(),
        "logo": build_logo_prompt(),
        "wording": build_wording_prompt(),
        "format": build_format_prompt(),
    }


# ============================================================
# 後方互換性のための旧関数
# ============================================================

def build_prompt(check_items: dict[str, bool] | None = None) -> str:
    """
    【非推奨】一括処理用プロンプト。後方互換性のために残す。
    新規コードは build_prompts_for_parallel を使用してください。
    """
    if check_items is None:
        check_items = {"atm": True, "logo": True, "wording": True, "format": True}

    rules = load_rules()
    prompt_parts = []

    prompt_parts.append("""あなたはセブン銀行の告知物（ポスター・チラシ・バナー・ATM画面告知等）を校閲するAIアシスタントです。

## 前提ルール（最重要）
- **チェック対象画像（画像6）に実際に存在するテキスト・要素のみを指摘すること**
- 画像内に存在しない語句を「ある」と誤認して指摘してはいけない
- 指摘する際は、必ず「該当箇所」に画像内で実際に確認できた具体的な文言を引用すること
- 判定に自信がない場合は **必ず「要目視確認」** とし、誤って「問題なし」としないこと
- 参照画像から読み取れるルールを最優先とし、不明点は「要確認」と明示すること
- チェック対象にATM画像やロゴが含まれない場合、そのチェックはスキップし「該当なし」と記載すること

## 参照画像の説明
- 参照画像1（atm_image_types.png）: ATM画像の5つの種類。原則①正面か②斜めを使用する。
- 参照画像2（atm_image_prohibitions.png）: ATM画像の4つの禁則。
- 参照画像3（logo_guide.png）: セブン銀行ロゴの形と色の規定。
- 参照画像4（logo_isolation_minsize.png）: ロゴ周囲の余白と最小使用サイズの規定。
- 参照画像5（wording_rules.png）: 表記ルール表。
- 画像6: チェック対象の告知物。""")

    prompt_parts.append("\n## チェック手順")

    if check_items.get("atm"):
        prompt_parts.append("""
### ATM画像チェック
1. チェック対象にATM画像が含まれるか確認
2. 含まれる場合、参照画像1と見比べて①〜⑤のどれに該当するか判定
3. 原則①正面か②斜めを使用。③〜⑤が使われていれば Warning
4. 参照画像2の禁則と見比べ、変形・回転・色変更・一部削除がないか確認
5. 明らかな違反は Fail、微妙な場合は Warning""")

    if check_items.get("logo"):
        prompt_parts.append("""
### ロゴチェック
1. チェック対象にセブン銀行ロゴが含まれるか確認
2. 含まれる場合、参照画像3と見比べてロゴの形・色が正規か確認
3. 参照画像4と見比べて余白が確保されているか確認
4. ロゴが極端に小さく使用されていないか確認
5. 明らかな違反のみ Fail、微妙な場合は Warning""")

    if check_items.get("wording"):
        wording_rules = rules.get("wording", [])
        prompt_parts.append("""
### 表記・ワーディングチェック
1. **まずチェック対象画像内のテキストを正確に読み取る**
2. 読み取ったテキストの中に、参照画像5の表記ルール表に該当する語句があるか確認
3. **画像内に存在しない語句を指摘してはいけない**""")
        if wording_rules:
            prompt_parts.append("\n**ワーディングルール：**")
            prompt_parts.append(_format_wording_rules(wording_rules))

    if check_items.get("format"):
        format_rules = rules.get("format", [])
        prompt_parts.append("""
### 形式チェック
1. 日付表記、金額表記、免責文言の有無等を確認""")
        if format_rules:
            prompt_parts.append("\n**フォーマットルール：**")
            prompt_parts.append(_format_format_rules(format_rules))

    prompt_parts.append("""
## 出力フォーマット
Markdownテンプレートで出力してください。
""")

    return "\n".join(prompt_parts)
