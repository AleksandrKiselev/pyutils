import os
import json
import re

# Путь к папке с JSON-файлами
folder_path = "d:\\AI-Software\\configs\\images\\model\\pony\\adrothver499\\nsfw\\.metadata"
output_txt = "D:\\AI-Software\\configs\\wildcards\\nsfw\\nsfw.txt"

prompts = []

# Получаем список JSON-файлов с абсолютным путем и временем создания
files = [
    (os.path.join(folder_path, f), os.path.getctime(os.path.join(folder_path, f)))
    for f in os.listdir(folder_path) if f.endswith(".json")
]

# Сортируем по времени создания
files.sort(key=lambda x: x[1], reverse=False)

# Обрабатываем файлы в порядке времени создания
for file_path, _ in files:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    prompt = data.get("prompt", "")
    prompt = re.sub(r'[ \t]*,(\\n|\n)?$', '', prompt)
    data["prompt"] = prompt

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    prompts.append(prompt)

os.makedirs(os.path.dirname(output_txt), exist_ok=True)

# Сохраняем все prompt в текстовый файл
with open(output_txt, "w", encoding="utf-8") as f:
    for p in prompts:
        f.write(p + "\n")