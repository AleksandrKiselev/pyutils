import json
import logging
from functools import lru_cache
from file_utils import walk_metadata


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_all_tags_cached():
    tag_set = set()
    for file in walk_metadata():
        try:
            with open(file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
                tag_set.update(metadata.get("tags", []))
        except Exception as e:
            logger.warning(f"Не удалось прочитать {file}: {e}")
    return sorted(tag_set)