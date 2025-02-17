import os
import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import transforms
from torch.utils.data import DataLoader, Dataset, random_split
from PIL import Image, UnidentifiedImageError
from loguru import logger
from model import CatClassifier, device, predict, image_size
from utils.save_load_model import save_model

# Подготовка данных
class CatsVsDogsDataset(Dataset):
    def __init__(self, root_dir, transform=None):
        self.root_dir = root_dir
        self.transform = transform
        self.files = []

        # Проверка файлов на корректность
        for label, sub_dir in enumerate(["Dog", "Cat"]):
            folder_path = os.path.join(root_dir, sub_dir)
            for file_name in os.listdir(folder_path):
                if file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff')):
                    full_path = os.path.join(folder_path, file_name)
                    try:
                        with Image.open(full_path) as img:
                            img.verify()  # Проверяем целостность изображения
                        self.files.append((full_path, label))
                    except (UnidentifiedImageError, OSError):
                        logger.warning(f"Skipping corrupted file: {full_path}")

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        img_path, label = self.files[idx]
        image = Image.open(img_path).convert("RGB")
        if self.transform:
            image = self.transform(image)
        return image, label

def main():
    # Гиперпараметры
    batch_size = 64
    num_epochs = 20
    learning_rate = 0.001

    transform = transforms.Compose([
        transforms.RandomHorizontalFlip(),  # Случайное горизонтальное отражение
        transforms.RandomRotation(20),  # Случайное вращение до 20 градусов
        transforms.Resize(image_size),  # Размер
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),  # Стандартные значения для RGB
    ])

    # Загрузка данных
    dataset_path = 'dataset/cats_vs_dogs/PetImages'
    all_data = CatsVsDogsDataset(dataset_path, transform=transform)

    # Разделение на обучающую и тестовую выборки
    train_size = int(0.8 * len(all_data))
    test_size = len(all_data) - train_size
    train_data, test_data = random_split(all_data, [train_size, test_size], generator=torch.Generator().manual_seed(42))

    train_loader = DataLoader(train_data, batch_size=batch_size, shuffle=True, num_workers=6)
    test_loader = DataLoader(test_data, batch_size=batch_size, shuffle=False)

    # Определение модели
    model = CatClassifier().to(device)

    # Используем BCELoss с логитами для бинарной классификации
    criterion = nn.BCEWithLogitsLoss()

    # Оптимизатор Adam
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    # Learning Rate Scheduler для динамического изменения темпа обучения
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.1)

    # Функция для обучения модели
    def train_model(model, train_loader, criterion, optimizer, epochs):
        model.train()
        for epoch in range(epochs):
            running_loss = 0.0
            for inputs, labels in train_loader:
                inputs, labels = inputs.to(device), labels.float().unsqueeze(1).to(device)

                optimizer.zero_grad()
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()

                running_loss += loss.item()
            logger.info(f"Epoch {epoch + 1}/{epochs}, Loss: {running_loss / len(train_loader):.4f}")
            scheduler.step()  # Обновление learning rate после каждого шага

    # Функция для оценки модели
    def evaluate_model(model, test_loader):
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for inputs, labels in test_loader:
                inputs, labels = inputs.to(device), labels.float().unsqueeze(1).to(device)
                outputs = model(inputs)
                predictions = (outputs > 0.5).float()
                correct += (predictions == labels).sum().item()
                total += labels.size(0)
        accuracy = correct / total
        logger.info(f"Accuracy: {accuracy:.2%}")
        return accuracy

    # Обучение и сохранение модели
    train_model(model, train_loader, criterion, optimizer, epochs=num_epochs)
    evaluate_model(model, test_loader)

    # Сохранение модели после обучения
    save_model(model, 'cat_classifier.safetensors')

    # Пример использования модели для предсказания
    test_image_path = 'dataset/cats_vs_dogs/PetImages/Cat/1.jpg'
    predict(model, test_image_path)


if __name__ == '__main__':
    # Здесь запускаем основной код
    import multiprocessing
    multiprocessing.set_start_method('spawn', force=True)  # Устанавливаем правильный метод старта процессов
    main()
