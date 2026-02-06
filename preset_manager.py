"""
プリセット管理モジュール

告知物タイプ・提携先に応じた追加ルールを管理する。
"""

from pathlib import Path
import yaml

PRESETS_FILE = Path(__file__).parent / "rules" / "presets.yaml"


def load_presets() -> dict:
    """presets.yaml を読み込む"""
    if not PRESETS_FILE.exists():
        return {"announcement_types": {}, "partners": {}}

    with open(PRESETS_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_announcement_types() -> dict[str, str]:
    """告知物タイプの一覧を返す {key: name}"""
    presets = load_presets()
    types = presets.get("announcement_types", {})
    return {key: val.get("name", key) for key, val in types.items()}


def get_partners() -> dict[str, str]:
    """提携先の一覧を返す {key: name}"""
    presets = load_presets()
    partners = presets.get("partners", {})
    return {key: val.get("name", key) for key, val in partners.items()}


def get_additional_rules(type_key: str, partner_key: str) -> list[str]:
    """
    選択されたタイプ・提携先の追加ルールを統合して返す。

    Parameters
    ----------
    type_key : str
        告知物タイプのキー（例: "sns_banner"）
    partner_key : str
        提携先のキー（例: "rakuten"）

    Returns
    -------
    list[str]
        適用される追加ルールのリスト
    """
    presets = load_presets()
    rules = []

    # 告知物タイプのルール
    types = presets.get("announcement_types", {})
    if type_key in types:
        rules.extend(types[type_key].get("rules", []))

    # 提携先のルール
    partners = presets.get("partners", {})
    if partner_key in partners:
        rules.extend(partners[partner_key].get("rules", []))

    return rules
