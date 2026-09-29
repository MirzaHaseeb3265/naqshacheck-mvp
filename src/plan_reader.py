from io import BytesIO
from pathlib import Path
import re

import fitz
from PIL import Image


DIMENSION_PATTERN = re.compile(r"(\d{1,3})\s*['’-]\s*(\d{1,2})?\s*[\"”]?", re.I)


def render_plan(file_bytes: bytes, filename: str) -> tuple[Image.Image, str]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        document = fitz.open(stream=file_bytes, filetype="pdf")
        page = document[0]
        text = page.get_text("text")
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
        image = Image.open(BytesIO(pixmap.tobytes("png"))).convert("RGB")
        return image, text
    image = Image.open(BytesIO(file_bytes)).convert("RGB")
    return image, ""


def find_dimension_candidates(text: str) -> list[str]:
    values = []
    for feet, inches in DIMENSION_PATTERN.findall(text):
        values.append(f"{feet}'-{inches or '0'}\"")
    return values[:20]

