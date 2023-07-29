import os
import re
import argparse


def main():
    parser = argparse.ArgumentParser(description="Delete files with specific pattern.")
    parser.add_argument("folder", help="The folder to search for files to delete.")

    args = parser.parse_args()
    folder = args.folder

    if os.path.exists(folder):
        pattern = re.compile(r'^(.+?) \(\d+\)\.\w+$')
        original_files = set()

        for root, _, files in os.walk(folder):
            for file in files:
                match = pattern.match(file)
                if match:
                    original_file = match.group(1) + os.path.splitext(file)[1]
                    if original_file in original_files:
                        file_path = os.path.join(root, file)
                        print(f"Deleting: {file_path}")
                        os.remove(file_path)
                    else:
                        original_files.add(original_file)
                else:
                    original_files.add(file)
        print("Deletion completed.")
    else:
        print("Folder not found.")


if __name__ == "__main__":
    main()
