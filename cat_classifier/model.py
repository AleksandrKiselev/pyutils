import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image
from loguru import logger

# Устройство (GPU или CPU)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

image_size = (256, 256)


class CatClassifier(nn.Module):
    def __init__(self):
        super(CatClassifier, self).__init__()

        # Загружаем базовую модель DenseNet без предобученных весов
        self.densenet = models.densenet121(pretrained=False)  # pretrained=False отключает предобученные веса

        # Модифицируем последний слой для бинарной классификации
        # В densenet121 последний слой имеет 1000 выходов (для ImageNet), мы изменим на 1 для бинарной классификации
        self.densenet.classifier = nn.Linear(self.densenet.classifier.in_features, 1)

    def forward(self, x):
        # Проходим через DenseNet
        x = self.densenet(x)
        return x  # Логиты для бинарной классификации


def predict(model, image_path):
    model.eval()
    image = Image.open(image_path).convert("RGB")
    transform = transforms.Compose([
        transforms.Resize(image_size),  # Размер до 256x256
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),  # Стандартные значения для RGB
    ])
    image = transform(image).unsqueeze(0).to(device)
    with torch.no_grad():
        output = model(image)
        probability = torch.sigmoid(output).item()  # Применяем сигмоиду для получения вероятности
        label = "Cat" if probability > 0.5 else "Dog"
    logger.info(f"Prediction for {image_path}: {label} (Probability: {probability:.2f})")
    return label, probability
