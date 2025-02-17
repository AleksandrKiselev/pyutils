import tkinter as tk
from tkinter import filedialog, Label
from PIL import Image, ImageTk, UnidentifiedImageError
from model import CatClassifier, predict, device, load_model

MAX_WIDTH = 600
MAX_HEIGHT = 400

# Загрузка модели
model = CatClassifier()
load_model(model, 'cat_classifier.safetensors')
model.to(device)
model.eval()

def open_file_dialog():
    """Обработчик кнопки для выбора файла"""
    file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff")])
    if file_path:
        load_image(file_path)


def load_image(file_path):
    """Функция загрузки изображения в UI"""
    global img_label, result_label

    try:
        # Открываем изображение
        image = Image.open(file_path).convert("RGB")
    except UnidentifiedImageError:
        result_label.config(text="Error: Invalid image file")
        return

    # Получаем размер изображения
    img_width, img_height = image.size
    aspect_ratio = img_width / img_height

    # Масштабируем изображение в зависимости от размеров окна
    window_width = 400  # можно задать размеры окна
    window_height = int(window_width * img_height / img_width)

    if window_width > MAX_WIDTH:
        window_width = MAX_WIDTH
        window_height = int(MAX_WIDTH / aspect_ratio)

    if img_height > MAX_HEIGHT:
        window_height = MAX_HEIGHT
        window_width = int(MAX_HEIGHT * aspect_ratio)

    image = image.resize((window_width, window_height), Image.Resampling.LANCZOS)

    photo = ImageTk.PhotoImage(image)

    # Обновляем Label для изображения
    img_label.config(image=photo, width=window_width, height=window_height)
    img_label.image = photo

    # Делаем предсказание и отображаем результат
    label, probability = predict(model, file_path)
    result_label.config(text=f"{label} (probability: {probability:.2f})")


# Создаем главное окно
root = tk.Tk()
root.title("Cat Classifier")

# Добавляем Label для изображения
img_label = Label(root, text="No image selected", width=40, height=20, relief="solid", bg="white")
img_label.grid(row=0, column=0, padx=10, pady=10)

# Добавляем Label для результата
result_label = Label(root, text="Prediction: None", font=("Arial", 16))
result_label.grid(row=1, column=0, padx=10, pady=10)

# Добавляем кнопку для выбора файла
choose_button = tk.Button(root, text="Choose Image", command=open_file_dialog)
choose_button.grid(row=2, column=0, padx=10, pady=10)

# Запускаем главное окно
root.mainloop()
