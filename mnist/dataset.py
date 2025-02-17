import os
from torchvision import datasets

def save_images(dataset_root, dataset, dataset_type='train'):
    dataset_path = os.path.join(dataset_root, dataset_type)
    os.makedirs(dataset_path, exist_ok=True)

    for idx, (image, label) in enumerate(dataset):
        # Создаём папку для текущего класса, если её нет
        class_folder = os.path.join(dataset_path, f'class_{label}')
        os.makedirs(class_folder, exist_ok=True)

        # Сохраняем изображение
        image.save(os.path.join(class_folder, f'{idx}.png'))

        # Опционально: выводим прогресс
        if idx % 1000 == 0:
            print(f'Saved {idx} images from {dataset_type} dataset')

    print(f'{dataset_type.capitalize()} dataset has been saved successfully.')


def main():
    dataset_root = './dataset'
    os.makedirs(dataset_root, exist_ok=True)

    mnist_train = datasets.MNIST(root=dataset_root, train=True, download=True)
    mnist_test = datasets.MNIST(root=dataset_root, train=False, download=True)

    save_images(dataset_root, mnist_train, dataset_type='train')
    save_images(dataset_root, mnist_test, dataset_type='test')


if __name__ == '__main__':
    main()