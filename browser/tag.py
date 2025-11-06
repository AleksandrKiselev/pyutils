"""
Извлечение, нормализация и управление тегами.
"""
import os
import json
import logging
import difflib
import re
import unicodedata
from functools import lru_cache
from typing import Set, List, Dict, Any, Optional
from paths import walk_metadata
from config import config
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
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


def auto_add_tags_from_prompt(image_path: str, metadata: Dict[str, Any], threshold: float = 0.90) -> None:
    tag_list = config.AUTO_TAGS
    prompt_lower = metadata.get("prompt", "").lower()

    prompt_clean = normalize_text(prompt_lower)
    prompt_token_set = set(prompt_clean.split())

    prompt_tokens = re.split(r"[.,:]", prompt_lower)
    normalized_tokens = [normalize_text(tok) for tok in prompt_tokens]

    normalized_tags = [(tag, normalize_text(tag)) for tag in tag_list]

    def check_tag(tag_tuple: tuple) -> Optional[str]:
        tag, tag_norm = tag_tuple
        
        if tag_norm in prompt_token_set:
            return tag
        
        tag_escaped = re.escape(tag_norm)
        if re.search(r'\b' + tag_escaped + r'\b', prompt_clean):
            return tag
        
        for norm_tok in normalized_tokens:
            if not norm_tok or abs(len(norm_tok) - len(tag_norm)) > 8:
                continue
            
            if len(tag_norm) > 2 and len(norm_tok) >= len(tag_norm) * 0.7:
                similarity = difflib.SequenceMatcher(None, norm_tok, tag_norm).ratio()
                if similarity >= threshold:
                    return tag
        return None

    try:
        with ThreadPoolExecutor() as executor:
            results = executor.map(check_tag, normalized_tags)
        prompt_tags = {tag for tag in results if tag}
    except Exception as e:
        logger.error(f"Ошибка обработки тегов для {image_path}: {e}")
        prompt_tags = set()

    auto_tags = set()
    auto_tags.update(get_image_tags(image_path))
    auto_tags.add(extract_seed(image_path))
    existing_tags = set(metadata.get("tags", []))
    combined = sorted(existing_tags.union(prompt_tags)) + list(auto_tags)
    metadata["tags"] = combined


@lru_cache(maxsize=1)
def get_all_tags_cached() -> List[str]:
    tags: Set[str] = set()
    for file in walk_metadata():
        try:
            with open(file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
                tags.update(metadata.get("tags", []))
        except json.JSONDecodeError as e:
            logger.warning(f"Не удалось распарсить JSON в {file}: {e}")
        except IOError as e:
            logger.warning(f"Не удалось прочитать {file}: {e}")
        except Exception as e:
            logger.warning(f"Неожиданная ошибка чтения {file}: {e}")
    
    return sorted(tags)