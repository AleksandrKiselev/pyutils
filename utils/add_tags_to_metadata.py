import os
import json

# === Настройки ===
ROOT_FOLDER = r"d:\AI-Software\configs\browser\static\images\char\rita"
NEW_TAGS = ["rita"]

def walk_metadata_files(root_folder):
    for root, dirs, files in os.walk(root_folder):
        if os.path.basename(root) == ".metadata":
            for file in files:
                if file.lower().endswith(".json"):
                    yield os.path.join(root, file)

def process_metadata_file(path, new_tags):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[!] Failed to load {path}: {e}")
        return

    old_tags = set(data.get("tags", []))
    added_tags = [tag for tag in new_tags if tag not in old_tags]

    if not added_tags and len(old_tags) == len(data.get("tags", [])):
        return

    data["tags"] = list(old_tags.union(new_tags))

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"[+] Updated: {path} (+{len(added_tags)} tags)")
    except Exception as e:
        print(f"[!] Failed to save {path}: {e}")

def main():
    for meta_file in walk_metadata_files(ROOT_FOLDER):
        process_metadata_file(meta_file, NEW_TAGS)

if __name__ == "__main__":
    main()
