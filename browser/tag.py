"""
Tag extraction, normalization, and management for the image browser application.
"""
import os
import json
import logging
import difflib
import re
import unicodedata
from functools import lru_cache
from file_utils import walk_metadata
from config import config
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

logger = logging.getLogger(__name__)

def get_image_tags(image_path):
    """Return a set of tags describing image orientation and resolution."""
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            orientation = "landscape" if width >= height else "portrait"
            resolution = f"{width}x{height}"
            return {orientation, resolution}
    except Exception as e:
        logger.warning(f"Failed to get image tags: {e}")
        return set()

def extract_seed(image_path):
    """Extract the seed from the image filename (without extension)."""
    base = os.path.basename(image_path)
    return os.path.splitext(base)[0]

def auto_add_tags_from_prompt(image_path, metadata, threshold=0.90):
    """Automatically add tags to metadata based on prompt and image properties."""
    tag_list = config.AUTO_TAGS
    prompt_lower = metadata.get("prompt", "").lower()
    prompt_tokens = re.split(r"[.,:]", prompt_lower)

    def normalize(text):
        text = unicodedata.normalize("NFKC", text.lower())
        text = text.strip(' \t\n"\'')
        # Replace special characters and normalize whitespace
        text = text.replace("-", " ").replace("_", " ")
        text = text.replace("’", "'").replace("`", "'")
        text = text.replace("“", '"').replace("”", '"')
        text = text.replace("…", "...")
        text = re.sub(r"[.,!?;:(){}\[\]]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def check_tag(tag):
        tag_lower = tag.lower()
        if tag_lower in prompt_lower:
            return tag
        for token in prompt_tokens:
            if difflib.SequenceMatcher(None, normalize(token), normalize(tag_lower)).ratio() >= threshold:
                return tag
        return None

    with ThreadPoolExecutor() as executor:
        results = executor.map(check_tag, tag_list)

    prompt_tags = {tag for tag in results if tag}
    auto_tags = set()
    auto_tags.update(get_image_tags(image_path))
    auto_tags.add(extract_seed(image_path))

    existing_tags = set(metadata.get("tags", []))
    combined = sorted(existing_tags.union(prompt_tags)) + list(auto_tags)
    metadata["tags"] = combined

@lru_cache(maxsize=1)
def get_all_tags_cached():
    """Return a sorted list of all unique tags from all metadata files."""
    tags = set()
    for file in walk_metadata():
        try:
            with open(file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
                tags.update(metadata.get("tags", []))
        except Exception as e:
            logger.warning(f"Failed to read {file}: {e}")
    return sorted(tags)