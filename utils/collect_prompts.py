import os
import json
import re

# Путь к папке с JSON-файлами
folder_path = "d:\\AI-Software\\configs\\browser\\static\\images\\nsfw"
output_txt = "d:\\AI-Software\\configs\\wildcards\\nsfw.txt"

prompts = []

for filename in os.listdir(folder_path):
    if filename.endswith(".json"):
        file_path = os.path.join(folder_path, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        prompt = data.get("prompt", "")
        prompt = re.sub(r'[ \t]*,(\\n|\n)?$', '', prompt)
        data["prompt"] = prompt

        # Сохраняем обратно в JSON
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        prompts.append(prompt)

# Сохраняем все prompt в текстовый файл
with open(output_txt, "w", encoding="utf-8") as f:
    prompts = sorted(prompts, key=lambda x: x.lower())
    for p in prompts:
        f.write(p + "\n")
