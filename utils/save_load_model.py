from safetensors.torch import save_file, load_file
from loguru import logger

# Сохранение модели в safetensors формат
def save_model(model, file_path):
    # Сохранение состояния модели в safetensors формат
    save_file(model.state_dict(), file_path)
    logger.info(f"Model saved at {file_path}")


# Загрузка модели из safetensors формата
def load_model(model, file_path):
    # Загрузка состояния модели из safetensors
    model.load_state_dict(load_file(file_path))
    model.eval()
    logger.info(f"Model loaded from {file_path}")