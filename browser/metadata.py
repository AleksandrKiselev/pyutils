"""
Metadata extraction, loading, and saving for images in the browser application.
"""
import json
import os
import re
import struct
import zlib
import logging
from functools import lru_cache
from file_utils import get_metadata_path
from tag import auto_add_tags_from_prompt

logger = logging.getLogger(__name__)

def extract_prompt_from_png(image_path):
    """Extract the prompt string from PNG metadata chunks."""
    try:
        with open(image_path, "rb") as f:
            data = f.read()

        chunks, offset = [], 8
        while offset < len(data):
            length = struct.unpack("!I", data[offset:offset+4])[0]
            chunk_type = data[offset+4:offset+8].decode("utf-8", "ignore")
            chunk_data = data[offset+8:offset+8+length]
            offset += 8 + length + 4

            if chunk_type == "zTXt":
                try:
                    null_index = chunk_data.index(b'\x00')
                    compressed = chunk_data[null_index + 2:]
                    decompressed = zlib.decompress(compressed).decode("utf-8", "ignore")
                    chunks.append(decompressed)
                except Exception as e:
                    logger.warning(f"Failed decompressing zTXt: {e}")
            elif chunk_type in ("tEXt", "iTXt"):
                chunks.append(chunk_data.decode("utf-8", "ignore"))

        metadata = "".join(chunks).strip()
        pattern = r'"title"\s*:\s*"PromptTextForBrowser",.*?"widgets_values"\s*:\s*\[\s*\[\s*"([^"]+)"\s*\]\s*\]'
        match = re.search(pattern, metadata, re.DOTALL)
        return match.group(1).strip() if match else "No metadata found"
    except Exception as e:
        logger.error(f"Error reading metadata: {e}")
        return "No metadata found"

@lru_cache(maxsize=512)
def load_metadata(image_path, mtime):
    """Load metadata for an image, creating defaults if necessary. Uses LRU cache for performance."""
    path = get_metadata_path(image_path)
    metadata = {}
    modified = False

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception as e:
            logger.warning(f"Corrupted metadata file: {path}, error: {e}")
            metadata = {}

    if "prompt" not in metadata:
        metadata["prompt"] = extract_prompt_from_png(image_path)
        modified = True
    if "checked" not in metadata:
        metadata["checked"] = False
        modified = True
    if "rating" not in metadata:
        metadata["rating"] = 0
        modified = True
    if "tags" not in metadata:
        auto_add_tags_from_prompt(image_path, metadata)
        modified = True

    if modified:
        save_metadata(image_path, metadata)

    return metadata

def save_metadata(image_path, metadata):
    """Save metadata for an image, auto-adding tags from prompt."""
    try:
        with open(get_metadata_path(image_path), "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Error saving metadata: {e}")
