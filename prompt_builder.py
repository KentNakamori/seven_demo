"""
プロンプト組み立てモジュール

選択されたチェック項目と rules.yaml の内容に基づいて、
Gemini API に送るプロンプトテキストを組み立てる。
"""

import yaml
from pathlib import Path

RULES_PATH = Path(__file__).parent / "rules" / "rules.yaml"

# 参照画像のキャプション定義（送信時に画像の前に挟む）
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


def build_prompt(check_items: dict[str, bool] | None = None) -> str:
    """
    校閲用プロンプトを組み立てて返す。

    Parameters
    ----------
    check_items : dict, optional
        チェック項目の有効/無効。None の場合は全項目有効。
        キー: "atm", "logo", "wording", "format"
    """
    if check_items is None:
        check_items = {"atm": True, "logo": True, "wording": True, "format": True}

    rules = load_rules()

    prompt_parts = []

    # --- システム指示 ---
    prompt_parts.append("""あなたはセブン銀行の告知物（ポスター・チラシ・バナー・ATM画面告知等）を校閲するAIアシスタントです。

## 前提ルール（最重要）
- **チェック対象画像（画像6）に実際に存在するテキスト・要素のみを指摘すること**
- 画像内に存在しない語句を「ある」と誤認して指摘してはいけない
- 指摘する際は、必ず「該当箇所」に画像内で実際に確認できた具体的な文言を引用すること
- 判定に自信がない場合は **必ず「要目視確認」** とし、誤って「問題なし」としないこと
- 参照画像から読み取れるルールを最優先とし、不明点は「要確認」と明示すること
- チェック対象にATM画像やロゴが含まれない場合、そのチェックはスキップし「該当なし」と記載すること

## 参照画像の説明
- 参照画像1（atm_image_types.png）: ATM画像の5つの種類。原則①正面か②斜めを使用する。③〜⑤はデザインのテイストでイラストが好ましい場合に限り使用可。
- 参照画像2（atm_image_prohibitions.png）: ATM画像の4つの禁則。①縦横比の変更・変形、②正体以外の配置・規定以外の向き、③異なるテイストの併用、④色の変更・一部の削除。
- 参照画像3（logo_guide.png）: セブン銀行ロゴの形と色の規定。コーポレートカラー（レッド、グリーン、オレンジ）または墨・白。
- 参照画像4（logo_isolation_minsize.png）: ロゴ周囲の余白（アイソレーション）と最小使用サイズの規定。
- 参照画像5（wording_rules.png）: 表記ルール表（送り仮名、読み、備考）。
- 画像6: チェック対象の告知物。""")

    # --- チェック手順 ---
    prompt_parts.append("\n## チェック手順")

    if check_items.get("atm"):
        prompt_parts.append("""
### ATM画像チェック
1. チェック対象（画像6）にATM画像が含まれるか確認
2. 含まれる場合、参照画像1と見比べて①〜⑤のどれに該当するか判定
3. 原則①正面か②斜めを使用。③〜⑤が使われていれば Warning
4. 参照画像2の禁則と見比べ、変形・回転・色変更・一部削除がないか確認
5. 明らかな違反は Fail、微妙な場合は Warning（要目視確認）""")

    if check_items.get("logo"):
        prompt_parts.append("""
### ロゴチェック
1. チェック対象にセブン銀行ロゴが含まれるか確認
2. 含まれる場合、参照画像3と見比べてロゴの形・色が正規か確認
3. 参照画像4と見比べて余白（アイソレーション）が確保されているか確認
4. ロゴが極端に小さく使用されていないか確認
5. 厳密なピクセル計測はできないため、明らかな違反のみ Fail、微妙な場合は Warning""")

    if check_items.get("wording"):
        wording_rules = rules.get("wording", [])
        prompt_parts.append("""
### 表記・ワーディングチェック
1. **まずチェック対象画像内のテキストを正確に読み取る**
2. 読み取ったテキストの中に、参照画像5の表記ルール表に該当する語句があるか確認
3. 読み取ったテキストの中に、以下の補助ルールに該当する語句があるか確認
4. **画像内に存在しない語句を指摘してはいけない** - 必ず画像から読み取った文言のみを対象とする""")
        if wording_rules:
            prompt_parts.append("\n**ワーディングルール：**")
            prompt_parts.append(_format_wording_rules(wording_rules))

    if check_items.get("format"):
        format_rules = rules.get("format", [])
        prompt_parts.append("""
### 形式チェック
1. 日付表記、金額表記、免責文言の有無等を確認
2. 以下のフォーマットルールに照らし合わせる""")
        if format_rules:
            prompt_parts.append("\n**フォーマットルール：**")
            prompt_parts.append(_format_format_rules(format_rules))

    # --- 出力フォーマット ---
    prompt_parts.append("""
## 出力フォーマット
以下のMarkdownテンプレートで出力してください。該当なしのセクションもスキップせず「該当なし」と記載してください。

```
# 校閲レポート

## サマリ

| Fail | Warning | Info |
|------|---------|------|
| N    | N       | N    |

---

## 指摘一覧

### ATM画像チェック
参照: atm_image_types.png, atm_image_prohibitions.png

| # | 重大度 | 指摘内容 | 根拠 | 該当箇所 | 次アクション |
|---|--------|---------|------|---------|------------|
| 1 | Fail/Warning/Info | 内容 | ルールID or 参照画像名 | 位置のヒント | 修正必須/要目視確認/問題なし |

### ロゴチェック
参照: logo_guide.png, logo_isolation_minsize.png

| # | 重大度 | 指摘内容 | 根拠 | 該当箇所 | 次アクション |
|---|--------|---------|------|---------|------------|
| 1 | Fail/Warning/Info | 内容 | ルールID or 参照画像名 | 位置のヒント | 修正必須/要目視確認/問題なし |

### 表記・ワーディングチェック
参照: wording_rules.png + rules.yaml

| # | 重大度 | 指摘内容 | 根拠 | 該当箇所 | 次アクション |
|---|--------|---------|------|---------|------------|
| 1 | Fail/Warning/Info | 内容 | ルールID or 参照画像名 | 位置のヒント | 修正必須/要目視確認/問題なし |

### 形式チェック
参照: rules.yaml

| # | 重大度 | 指摘内容 | 根拠 | 該当箇所 | 次アクション |
|---|--------|---------|------|---------|------------|
| 1 | Fail/Warning/Info | 内容 | ルールID | 位置のヒント | 修正必須/要目視確認/問題なし |

---

## 目視確認リスト
以下の項目は自動判定に限界があるため、担当者による目視確認をお願いします。

- [ ] 確認項目1
- [ ] 確認項目2

---

## 備考
- 本レポートはAIの画像認識による簡易チェック結果です
- 厳密なピクセル計測や色値判定は含まれていません
- 法令（景表法等）の適合判断は対象外です
```""")

    return "\n".join(prompt_parts)
