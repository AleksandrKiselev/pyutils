import shutil
import os
import argparse


def main():
    parser = argparse.ArgumentParser(description="Move files from source folder to destination folder.")
    parser.add_argument("source_folder", help="The folder from where to copy the files.")
    parser.add_argument("destination_folder", help="The folder where to copy the files to.")

    args = parser.parse_args()

    source_folder = args.source_folder
    destination_folder = args.destination_folder

    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)

    if os.path.exists(source_folder):
        for root, dirs, files in os.walk(source_folder):
            for file in files:
                file_path = os.path.join(root, file)
                destination_path = os.path.join(destination_folder, file)

                if os.path.exists(destination_path):
                    base, extension = os.path.splitext(file)
                    count = 1
                    while os.path.exists(os.path.join(destination_folder, f"{base} ({count}){extension}")):
                        count += 1
                    destination_path = os.path.join(destination_folder, f"{base} ({count}){extension}")

                shutil.move(file_path, destination_path)
        print("File transfer completed.")
    else:
        print("Source folder not found.")


if __name__ == "__main__":
    main()
