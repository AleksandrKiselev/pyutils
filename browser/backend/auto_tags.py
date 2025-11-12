"""Модуль для автоматической генерации тегов используя WD14 Tagger."""

import os
import logging
import threading
from typing import List, Optional

try:
    from config import config
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False

logger = logging.getLogger(__name__)

WD14_AVAILABLE = False
try:
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download
    from PIL import Image
    import numpy as np
    import cv2
    import pandas as pd
    WD14_AVAILABLE = True
except ImportError:
    pass

_wd14_model_cache = None
_wd14_tags_cache = None
_wd14_loading_lock = threading.Lock()
_wd14_loading = False


def make_square(img, target_size):
    """Делает изображение квадратным, добавляя белые границы"""
    old_size = img.shape[:2]
    desired_size = max(old_size)
    desired_size = max(desired_size, target_size)
    delta_w = desired_size - old_size[1]
    delta_h = desired_size - old_size[0]
    top, bottom = delta_h // 2, delta_h - (delta_h // 2)
    left, right = delta_w // 2, delta_w - (delta_w // 2)
    color = [255, 255, 255]
    return cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)


def smart_resize(img, size):
    """Умный ресайз с разными интерполяциями в зависимости от размера"""
    if img.shape[0] > size:
        img = cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)
    elif img.shape[0] < size:
        img = cv2.resize(img, (size, size), interpolation=cv2.INTER_CUBIC)
    return img


class AutoTagGenerator:
    """Генератор автоматических тегов для изображений используя WD14 Tagger"""
    
    def __init__(self):
        """Инициализация генератора тегов"""
        self._model = None
        self._tags_df = None
    
    def _load_wd14_model(self):
        """Загружает WD14 Tagger модель с Hugging Face"""
        global _wd14_model_cache, _wd14_tags_cache, _wd14_loading_lock, _wd14_loading
        
        if not WD14_AVAILABLE:
            raise ImportError("onnxruntime и huggingface_hub не установлены. Установите: pip install onnxruntime huggingface_hub")
        
        if _wd14_model_cache is not None:
            self._model = _wd14_model_cache
            self._tags_df = _wd14_tags_cache
            return
        
        with _wd14_loading_lock:
            if _wd14_model_cache is not None:
                self._model = _wd14_model_cache
                self._tags_df = _wd14_tags_cache
                return
            
            if _wd14_loading:
                while _wd14_loading:
                    import time
                    time.sleep(0.1)
                if _wd14_model_cache is not None:
                    self._model = _wd14_model_cache
                    self._tags_df = _wd14_tags_cache
                    return
            
            _wd14_loading = True
            
            try:
                logger.info("Загрузка WD14 Tagger модели с Hugging Face...")
                model_repo = "SmilingWolf/wd-v1-4-swinv2-tagger-v2"
                
                model_path = hf_hub_download(
                    repo_id=model_repo,
                    filename="model.onnx",
                    cache_dir=None
                )
                
                tags_path = hf_hub_download(
                    repo_id=model_repo,
                    filename="selected_tags.csv",
                    cache_dir=None
                )
                
                available_providers = ort.get_available_providers()
                logger.info(f"Доступные ONNX Runtime провайдеры: {available_providers}")
                
                model = None
                if 'CUDAExecutionProvider' in available_providers:
                    try:
                        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
                        model = ort.InferenceSession(model_path, providers=providers)
                        actual_providers = model.get_providers()
                        if 'CUDAExecutionProvider' in actual_providers:
                            logger.info("WD14 Tagger использует GPU (CUDA)")
                        else:
                            logger.info("WD14 Tagger использует CPU")
                    except Exception as e:
                        logger.warning(f"Не удалось использовать CUDA: {e}")
                        model = None
                
                if model is None:
                    try:
                        providers = ['CPUExecutionProvider']
                        model = ort.InferenceSession(model_path, providers=providers)
                        logger.info("WD14 Tagger использует CPU")
                    except Exception as e:
                        logger.error(f"Не удалось создать ONNX Runtime сессию даже на CPU: {e}")
                        raise
                
                output_shape = model.get_outputs()[0].shape
                expected_num_tags = output_shape[1] if len(output_shape) > 1 else output_shape[0]
                logger.info(f"Модель ожидает {expected_num_tags} тегов (размер выхода: {output_shape})")
                
                tags_df = pd.read_csv(tags_path)
                logger.info(f"Загружено {len(tags_df)} тегов из CSV файла")
                
                if len(tags_df) != expected_num_tags:
                    logger.info(f"CSV содержит {len(tags_df)} тегов, модель возвращает {expected_num_tags} вероятностей")
                
                _wd14_model_cache = model
                _wd14_tags_cache = tags_df
                self._model = model
                self._tags_df = tags_df
                
                logger.info(f"WD14 Tagger модель загружена. Тегов в словаре: {len(tags_df)}")
                
            except Exception as e:
                logger.error(f"Ошибка загрузки WD14 модели: {e}")
                raise
            finally:
                _wd14_loading = False
    
    def generate_tags(self, image_path: str, threshold: float = 0.3771, top_k: int = 20) -> List[str]:
        """
        Генерирует теги используя WD14 Tagger от SmilingWolf
        
        Args:
            image_path: Путь к изображению
            threshold: Порог вероятности для включения тега (по умолчанию 0.3771 - оптимальный согласно README)
            top_k: Максимальное количество тегов
        
        Returns:
            Список тегов
        """
        if not WD14_AVAILABLE:
            logger.warning("WD14 Tagger недоступен. Установите: pip install onnxruntime huggingface_hub")
            return []
        
        try:
            self._load_wd14_model()
            
            image = Image.open(image_path)
            _, target_size, _, _ = self._model.get_inputs()[0].shape
            
            image = image.convert('RGBA')
            new_image = Image.new('RGBA', image.size, 'WHITE')
            new_image.paste(image, mask=image)
            image = new_image.convert('RGB')
            image = np.asarray(image)
            
            image = make_square(image, target_size)
            image = smart_resize(image, target_size)
            image = image.astype(np.float32)
            image = np.expand_dims(image, 0)
            
            logger.debug(f"Обработанное изображение: форма {image.shape}, диапазон [{image.min():.3f}, {image.max():.3f}]")
            
            input_name = self._model.get_inputs()[0].name
            label_name = self._model.get_outputs()[0].name
            confidence = self._model.run([label_name], {input_name: image})[0]
            
            logger.debug(f"Получено {len(confidence[0])} вероятностей")
            
            full_tags = self._tags_df[['name', 'category']].copy()
            full_tags['confidence'] = confidence[0]
            tags_df = full_tags[full_tags['category'] != 9].copy()
            filtered_tags = tags_df[tags_df['confidence'] >= threshold]
            filtered_tags = filtered_tags.sort_values('confidence', ascending=False)
            top_tags = filtered_tags.head(top_k)
            
            if len(top_tags) > 0:
                top_tags_debug = ", ".join([f"{row['name']}({row['confidence']:.3f})" for _, row in top_tags.head(10).iterrows()])
                logger.debug(f"Топ-10 тегов для {os.path.basename(image_path)}: {top_tags_debug}")
            
            tags = [tag.replace('_', ' ') for tag in top_tags['name'].tolist()]
            return tags
                
        except ImportError as e:
            logger.warning(f"WD14 Tagger не установлен: {e}")
            logger.info("Установите: pip install onnxruntime huggingface_hub")
            return []
        except Exception as e:
            logger.warning(f"Ошибка генерации тегов WD14 для {image_path}: {e}")
            return []


_tag_generator: Optional[AutoTagGenerator] = None


def get_auto_tags(image_path: str, enabled: bool = True, threshold: Optional[float] = None) -> List[str]:
    """
    Генерирует автоматические теги для изображения используя WD14 Tagger
    
    Args:
        image_path: Путь к изображению
        enabled: Включена ли автоматическая генерация тегов
        threshold: Порог вероятности (если None, используется из config)
    
    Returns:
        Список тегов
    """
    if not enabled:
        return []
    
    if not WD14_AVAILABLE:
        logger.warning("WD14 Tagger недоступен. Установите: pip install onnxruntime huggingface_hub")
        return []
    
    global _tag_generator
    
    try:
        if _tag_generator is None:
            _tag_generator = AutoTagGenerator()
        
        if threshold is None:
            threshold = 0.3771
            if CONFIG_AVAILABLE and hasattr(config, 'AUTO_TAG_THRESHOLD'):
                threshold = config.AUTO_TAG_THRESHOLD
        
        return _tag_generator.generate_tags(image_path, threshold=threshold)
    except Exception as e:
        logger.warning(f"Ошибка автоматической генерации тегов для {image_path}: {e}")
        return []
