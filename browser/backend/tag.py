"""
Извлечение, нормализация и управление тегами.
"""
import os
import logging
import re
import unicodedata
from typing import Set, Dict, Any
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
            return {orientation, resolution}
    except Exception as e:
        logger.warning(f"Не удалось получить теги изображения для {image_path}: {e}")
        return set()


def extract_seed(image_path: str) -> str:
    base = os.path.basename(image_path)
    return os.path.splitext(base)[0]


def add_tags_from_prompt(image_path: str, metadata: Dict[str, Any], threshold: float = 0.9) -> None:
    prompt = metadata.get("prompt", "").lower()
    prompt_tags = list()
    if prompt:
        all_tags = [normalize(tag.lower()) for tag in config.AUTO_TAGS]
        tokens = [
            normalize(token.lower())
            for token in re.split(r"[.,:]|\bBREAK\b", prompt, flags=re.IGNORECASE)
            if token.strip()
        ]

        def check_tag(tag):
            if tag in prompt:
                return True
            for token in tokens:
                if fuzz.ratio(token, tag) / 100.0 >= threshold:
                    return True
            return False

        prompt_tags = {tag for tag in all_tags if check_tag(tag)}

    image_tags = get_image_tags(image_path)
    image_tags.add(extract_seed(image_path))
    metadata["tags"] = sorted(prompt_tags) + list(image_tags)