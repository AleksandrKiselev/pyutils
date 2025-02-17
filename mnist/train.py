import os
import torch
import torch.nn as nn
import torch.optim as optim
from tqdm import tqdm
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, transforms
from loguru import logger
from model import LinearModel
from utils.save_load_model import save_model


def eval_model(device, model, eval_loader, criterion):
    model.eval()
    with torch.no_grad():  # Отключаем градиенты для оценки
        for inputs, labels in eval_loader:
            inputs = inputs.reshape(-1, 28 * 28).to(device)
            labels = labels.reshape(-1).to(torch.float32)
            labels = torch.eye(10)[labels].to(device)

            # Прямой проход + расчет ошибки
            outputs = model(inputs)
            loss = criterion(outputs, labels)


def train_model(device, model, train_loader, val_loader, criterion, optimizer, epochs=5):
    for epoch in range(epochs):
        # Тренировка
        model.train()
        running_train_loss = []
        train_loop = tqdm(train_loader, leave=False)
        for i, (inputs, labels) in enumerate(train_loader):
            inputs = inputs.reshape(-1, 28*28).to(device)
            labels = labels.reshape(-1).to(torch.float32)
            labels = torch.eye(10)[labels].to(device)

            # Прямой проход + расчет ошибки
            outputs = model(inputs)
            loss = criterion(outputs, labels)

            # Обратный проход + шаг оптимизации
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            # Расчет метрики
            running_train_loss.append(loss.item())
            mean_train_loss = sum(running_train_loss) / len(running_train_loss)
            train_loop.set_description(f'Epoch [{epoch+1}/{epochs}], train_loss={mean_train_loss:.4f}')

        # Валидация
        eval_model(device, model, val_loader, criterion)

    logger.info('Training completed.')


def main():
    dataset_root = './dataset'
    batch_size = 16
    num_epochs = 5
    learning_rate = 0.001

    # Преобразования для изображений
    transform = transforms.Compose([
        transforms.Grayscale(num_output_channels=1),
        transforms.ToTensor(),
        transforms.Normalize((0.5,), (0.5,))
    ])

    train_data = datasets.ImageFolder(root=os.path.join(dataset_root, 'train'), transform=transform)
    test_data = datasets.ImageFolder(root=os.path.join(dataset_root, 'test'), transform=transform)
    train_data, val_data = random_split(train_data, [0.8, 0.2])
    logger.info(f'Train images: {len(train_data)}')
    logger.info(f'Val images: {len(val_data)}')
    logger.info(f'Test images: {len(test_data)}')

    train_loader = DataLoader(train_data, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_data, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_data, batch_size=batch_size, shuffle=False)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # Инициализация модели, функции потерь и оптимизатора
    model = LinearModel(28*28, 10).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    # Запуск обучения
    train_model(device, model, train_loader, val_loader, criterion, optimizer, epochs=num_epochs)

    save_model(model, 'mnist.safetensors')


if __name__ == '__main__':
    main()
