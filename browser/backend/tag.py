"""
Извлечение, нормализация и управление тегами.
"""
import os
import logging
import re
import unicodedata
from typing import Set, List
from rapidfuzz import fuzz
from config import config
from PIL import Image

logger = logging.getLogger(__name__)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.lower())
    text = text.strip(' \t\n"\'')
    text = text.replace("-", " ").replace("_", " ")
    text = text.replace("'", "'").replace("`", "'")
    text = text.replace(""", '"').replace(""", '"')
    text = text.replace("…", "...")
    text = re.sub(r"[.,!?;:(){}\[\]]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_image_tags(image_path: str) -> Set[str]:
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            orientation = "landscape" if width >= height else "portrait"
            resolution = f"{width}x{height}"
        ext = os.path.splitext(image_path)[1].lower().lstrip(".")
        return {orientation, resolution, ext}
    except Exception as e:
        logger.warning(f"Не удалось получить теги изображения для {image_path}: {e}")
        return set()


def extract_tags_from_prompt(image_path: str, prompt: str, threshold: float = 0.9) -> List[str]:
    """Извлекает теги из промпта и изображения. При ошибке возвращает пустой список."""
    try:
        prompt_tags = set()
        if prompt:
            prompt_lower = prompt.lower()
            all_tags = [normalize(tag.lower()) for tag in config.AUTO_TAGS]
            tokens = [
                normalize(token.lower())
                for token in re.split(r"[.,:]|\bBREAK\b", prompt_lower, flags=re.IGNORECASE)
                if token.strip()
            ]

            def check_tag(tag):
                if tag in prompt_lower:
                    return True
                for token in tokens:
                    if fuzz.ratio(token, tag) / 100.0 >= threshold:
                        return True
                return False

            prompt_tags = {tag for tag in all_tags if check_tag(tag)}

        image_tags = get_image_tags(image_path)
        return sorted(prompt_tags | image_tags)
    except Exception as e:
        logger.warning(f"Ошибка извлечения тегов для {image_path}: {e}")
        return []