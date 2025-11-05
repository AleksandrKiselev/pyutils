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
from typing import Set, List, Dict, Any, Optional
from paths import walk_metadata
from config import config
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from exceptions import FileOperationError

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """
    Normalize text for tag matching: unicode normalization, lowercasing, and cleanup.
    
    Args:
        text: Text to normalize
        
    Returns:
        Normalized text string
    """
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
    """
    Return a set of tags describing image orientation and resolution.
    
    Args:
        image_path: Absolute path to the image file
        
    Returns:
        Set of tags (orientation and resolution)
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            orientation = "landscape" if width >= height else "portrait"
            resolution = f"{width}x{height}"
            return {orientation, resolution}
    except Exception as e:
        logger.warning(f"Failed to get image tags for {image_path}: {e}")
        return set()


def extract_seed(image_path: str) -> str:
    """
    Extract the seed from the image filename (without extension).
    
    Args:
        image_path: Absolute path to the image file
        
    Returns:
        Filename without extension (seed)
    """
    base = os.path.basename(image_path)
    return os.path.splitext(base)[0]


def auto_add_tags_from_prompt(image_path: str, metadata: Dict[str, Any], threshold: float = 0.90) -> None:
    """
    Automatically add tags to metadata based on prompt and image properties.
    
    Uses parallel processing for tag matching and fuzzy matching for typos.
    
    Args:
        image_path: Absolute path to the image file
        metadata: Metadata dictionary to update (modified in place)
        threshold: Similarity threshold for fuzzy matching (default: 0.90)
    """
    tag_list = config.AUTO_TAGS
    prompt_lower = metadata.get("prompt", "").lower()

    # Normalize prompt for matching
    prompt_clean = normalize_text(prompt_lower)
    prompt_token_set = set(prompt_clean.split())

    # Split prompt into tokens for fuzzy matching
    prompt_tokens = re.split(r"[.,:]", prompt_lower)
    normalized_tokens = [normalize_text(tok) for tok in prompt_tokens]

    # Normalize all tags for comparison
    normalized_tags = [(tag, normalize_text(tag)) for tag in tag_list]

    def check_tag(tag_tuple: tuple) -> Optional[str]:
        """
        Check if a tag matches the prompt (optimized for parallel execution).
        
        Args:
            tag_tuple: Tuple of (tag, normalized_tag)
            
        Returns:
            Tag name if match found, None otherwise
        """
        tag, tag_norm = tag_tuple
        
        # Exact word match: check token set first (fast)
        if tag_norm in prompt_token_set:
            return tag
        
        # Check with word boundaries to avoid substring matches
        tag_escaped = re.escape(tag_norm)
        if re.search(r'\b' + tag_escaped + r'\b', prompt_clean):
            return tag
        
        # Fuzzy match for typos: only match whole tokens, not substrings
        for norm_tok in normalized_tokens:
            # Skip if lengths are too different
            if not norm_tok or abs(len(norm_tok) - len(tag_norm)) > 8:
                continue
            
            # Only match if lengths are similar (prevents "ass" matching "assistant")
            if len(tag_norm) > 2 and len(norm_tok) >= len(tag_norm) * 0.7:
                similarity = difflib.SequenceMatcher(None, norm_tok, tag_norm).ratio()
                if similarity >= threshold:
                    return tag
        return None

    # Parallel processing of tags using thread pool
    try:
        with ThreadPoolExecutor() as executor:
            results = executor.map(check_tag, normalized_tags)
        prompt_tags = {tag for tag in results if tag}
    except Exception as e:
        logger.error(f"Error processing tags for {image_path}: {e}")
        prompt_tags = set()

    # Combine all tags
    auto_tags = set()
    auto_tags.update(get_image_tags(image_path))
    auto_tags.add(extract_seed(image_path))
    existing_tags = set(metadata.get("tags", []))
    combined = sorted(existing_tags.union(prompt_tags)) + list(auto_tags)
    metadata["tags"] = combined


@lru_cache(maxsize=1)
def get_all_tags_cached() -> List[str]:
    """
    Return a sorted list of all unique tags from all metadata files.
    
    Uses LRU cache to avoid re-reading all metadata files on every call.
    Cache should be cleared when metadata is updated.
    
    Returns:
        Sorted list of unique tag strings
        
    Raises:
        FileOperationError: If metadata files cannot be read
    """
    tags: Set[str] = set()
    for file in walk_metadata():
        try:
            with open(file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
                tags.update(metadata.get("tags", []))
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON in {file}: {e}")
        except IOError as e:
            logger.warning(f"Failed to read {file}: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error reading {file}: {e}")
    
    return sorted(tags)