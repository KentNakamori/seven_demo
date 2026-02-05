"""
Gemini API 呼び出しモジュール（分割並列処理版）

チェックカテゴリごとに必要な参照画像のみを送信し、
並列でAPIを呼び出して結果を統合する。
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from dataclasses import dataclass

import google.generativeai as genai
from PIL import Image

REFERENCES_DIR = Path(__file__).parent / "references"

# チェックカテゴリごとの参照画像定義
CHECK_CONFIGS = {
    "atm": {
        "name": "ATM画像チェック",
        "files": ["atm_image_types.png", "atm_image_prohibitions.png"],
        "captions": [
            "参照画像1（ATM画像の種類ルール）：",
            "参照画像2（ATM画像の禁則事項）：",
        ],
    },
    "logo": {
        "name": "ロゴチェック",
        "files": ["logo_guide.png", "logo_isolation_minsize.png"],
        "captions": [
            "参照画像1（ロゴの形・色の規定）：",
            "参照画像2（ロゴのアイソレーション・最小サイズ規定）：",
        ],
    },
    "wording": {
        "name": "表記・ワーディングチェック",
        "files": [],  # 参照画像なし（YAMLルールで十分、処理軽量化）
        "captions": [],
    },
    "format": {
        "name": "形式チェック",
        "files": [],  # 参照画像なし（YAMLルールのみ）
        "captions": [],
    },
}

MAX_IMAGE_SIZE = 1500


@dataclass
class CheckResult:
    """個別チェックの結果"""
    category: str
    name: str
    result_text: str
    success: bool
    error: str | None = None


def _resize_image(img: Image.Image, max_size: int = MAX_IMAGE_SIZE) -> Image.Image:
    """長辺が max_size を超える場合にリサイズする。"""
    w, h = img.size
    if max(w, h) <= max_size:
        return img
    if w >= h:
        new_w = max_size
        new_h = int(h * max_size / w)
    else:
        new_h = max_size
        new_w = int(w * max_size / h)
    return img.resize((new_w, new_h), Image.LANCZOS)


def _load_reference_images(file_names: list[str]) -> list[Image.Image]:
    """指定された参照画像を読み込み、リサイズして返す。"""
    images = []
    for fname in file_names:
        path = REFERENCES_DIR / fname
        if not path.exists():
            raise FileNotFoundError(f"参照画像が見つかりません: {path}")
        img = Image.open(path).convert("RGB")
        images.append(_resize_image(img))
    return images


def configure_api(api_key: str | None = None) -> None:
    """Gemini API を設定する。"""
    key = api_key or os.getenv("GEMINI_API_KEY")

    # Streamlit Cloud の Secrets からも取得を試みる
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            pass

    if not key:
        raise ValueError(
            "GEMINI_API_KEY が設定されていません。"
            ".env ファイルまたは Streamlit Secrets で設定してください。"
        )
    genai.configure(api_key=key)


# API呼び出しのタイムアウト（秒）
API_TIMEOUT = 120


def _run_single_check(
    category: str,
    target_image: Image.Image,
    prompt_text: str,
    model_name: str,
) -> CheckResult:
    """単一カテゴリのチェックを実行する。"""
    config = CHECK_CONFIGS[category]
    start_time = time.time()
    print(f"[{category}] チェック開始...")

    try:
        # コンテンツ構築
        contents: list = []

        # 参照画像がある場合のみ追加
        if config["files"]:
            ref_images = _load_reference_images(config["files"])
            for caption, img in zip(config["captions"], ref_images):
                contents.append(caption)
                contents.append(img)

        # チェック対象画像
        contents.append("以下がチェック対象の告知物です：")
        contents.append(target_image)
        contents.append(prompt_text)

        # API呼び出し
        generation_config = genai.GenerationConfig(
            temperature=0,
            top_p=1,
            top_k=1,
        )

        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            contents,
            generation_config=generation_config,
            request_options={"timeout": API_TIMEOUT},
        )

        elapsed = time.time() - start_time
        print(f"[{category}] 完了 ({elapsed:.1f}秒)")

        return CheckResult(
            category=category,
            name=config["name"],
            result_text=response.text,
            success=True,
        )

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[{category}] エラー ({elapsed:.1f}秒): {e}")
        return CheckResult(
            category=category,
            name=config["name"],
            result_text="",
            success=False,
            error=str(e),
        )


def run_proofread_parallel(
    target_image: Image.Image,
    prompts: dict[str, str],
    model_name: str = "gemini-2.5-pro",
    check_items: dict[str, bool] | None = None,
) -> list[CheckResult]:
    """
    分割並列で校閲を実行して結果リストを返す。

    Parameters
    ----------
    target_image : PIL.Image.Image
        チェック対象の画像
    prompts : dict[str, str]
        カテゴリごとのプロンプト {"atm": "...", "logo": "...", ...}
    model_name : str
        使用する Gemini モデル名
    check_items : dict[str, bool], optional
        チェック項目の有効/無効

    Returns
    -------
    list[CheckResult]
        各カテゴリの校閲結果
    """
    if check_items is None:
        check_items = {"atm": True, "logo": True, "wording": True, "format": True}

    # 対象画像をリサイズ
    target_resized = _resize_image(target_image.convert("RGB"))

    # 有効なチェック項目のみ実行
    active_categories = [cat for cat, enabled in check_items.items() if enabled]

    # ThreadPoolExecutorで並列実行
    results: list[CheckResult] = []
    total_start = time.time()
    print(f"\n=== 並列処理開始 ({len(active_categories)}カテゴリ) ===")

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(
                _run_single_check,
                category,
                target_resized,
                prompts.get(category, ""),
                model_name,
            ): category
            for category in active_categories
        }

        # as_completed で完了順に結果を取得
        for future in as_completed(futures, timeout=API_TIMEOUT + 30):
            category = futures[future]
            try:
                result = future.result()
                results.append(result)
            except TimeoutError:
                results.append(CheckResult(
                    category=category,
                    name=CHECK_CONFIGS[category]["name"],
                    result_text="",
                    success=False,
                    error=f"タイムアウト（{API_TIMEOUT}秒以上応答なし）",
                ))
            except Exception as e:
                results.append(CheckResult(
                    category=category,
                    name=CHECK_CONFIGS[category]["name"],
                    result_text="",
                    success=False,
                    error=str(e),
                ))

    total_elapsed = time.time() - total_start
    print(f"=== 並列処理完了 (合計 {total_elapsed:.1f}秒) ===\n")

    # カテゴリ順にソート
    category_order = ["atm", "logo", "wording", "format"]
    results.sort(key=lambda r: category_order.index(r.category) if r.category in category_order else 99)

    return results


# 後方互換性のため、旧関数も残す（非推奨）
def run_proofread(
    target_image: Image.Image,
    prompt_text: str,
    model_name: str = "gemini-2.5-pro",
) -> str:
    """
    【非推奨】一括処理版。後方互換性のために残す。
    新規コードは run_proofread_parallel を使用してください。
    """
    from prompt_builder import REFERENCE_CAPTIONS

    REFERENCE_FILES = [
        "atm_image_types.png",
        "atm_image_prohibitions.png",
        "logo_guide.png",
        "logo_isolation_minsize.png",
        "wording_rules.png",
    ]

    ref_images = _load_reference_images(REFERENCE_FILES)
    target_resized = _resize_image(target_image.convert("RGB"))

    contents: list = []
    for caption, img in zip(REFERENCE_CAPTIONS, ref_images):
        contents.append(caption)
        contents.append(img)

    contents.append("以下がチェック対象の告知物です：")
    contents.append(target_resized)
    contents.append(prompt_text)

    generation_config = genai.GenerationConfig(
        temperature=0,
        top_p=1,
        top_k=1,
    )

    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        contents,
        generation_config=generation_config,
    )

    return response.text
