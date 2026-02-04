"""
Gemini API 呼び出しモジュール

参照画像（キャプション付き）とチェック対象画像をマルチモーダルで送信し、
校閲結果を受け取る。
"""

import os
from pathlib import Path

import google.generativeai as genai
from PIL import Image

from prompt_builder import REFERENCE_CAPTIONS

REFERENCES_DIR = Path(__file__).parent / "references"

# 参照画像ファイルの順序（キャプションと対応）
REFERENCE_FILES = [
    "atm_image_types.png",
    "atm_image_prohibitions.png",
    "logo_guide.png",
    "logo_isolation_minsize.png",
    "wording_rules.png",
]

MAX_IMAGE_SIZE = 1500  # 長辺の最大ピクセル数


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


def load_reference_images() -> list[Image.Image]:
    """参照画像を読み込み、リサイズして返す。"""
    images = []
    for fname in REFERENCE_FILES:
        path = REFERENCES_DIR / fname
        if not path.exists():
            raise FileNotFoundError(f"参照画像が見つかりません: {path}")
        img = Image.open(path).convert("RGB")
        images.append(_resize_image(img))
    return images


def configure_api(api_key: str | None = None) -> None:
    """Gemini API を設定する。"""
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError(
            "GEMINI_API_KEY が設定されていません。"
            ".env ファイルまたは環境変数で設定してください。"
        )
    genai.configure(api_key=key)


def run_proofread(
    target_image: Image.Image,
    prompt_text: str,
    model_name: str = "gemini-2.0-flash",
) -> str:
    """
    校閲を実行して結果テキストを返す。

    Parameters
    ----------
    target_image : PIL.Image.Image
        チェック対象の画像
    prompt_text : str
        prompt_builder.build_prompt() で生成したプロンプト
    model_name : str
        使用する Gemini モデル名

    Returns
    -------
    str
        校閲結果（Markdown テキスト）
    """
    ref_images = load_reference_images()
    target_resized = _resize_image(target_image.convert("RGB"))

    # キャプション付きで画像を交互に配置
    contents: list = []
    for caption, img in zip(REFERENCE_CAPTIONS, ref_images):
        contents.append(caption)
        contents.append(img)

    contents.append("以下がチェック対象の告知物です：")
    contents.append(target_resized)
    contents.append(prompt_text)

    model = genai.GenerativeModel(model_name)
    response = model.generate_content(contents)

    return response.text
