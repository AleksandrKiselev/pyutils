import os
import re
import tkinter as tk
from tkinter import filedialog


def rename_files_recursively(directory, old_name_pattern, new_name):
    old_name_re = re.compile(old_name_pattern)

    for root, dirs, files in os.walk(directory):
        for file in files:
            if old_name_re.match(file):
                old_file_path = os.path.join(root, file)
                new_file_path = os.path.join(root, new_name)
                os.rename(old_file_path, new_file_path)
                log_message = f"Renamed: {old_file_path} -> {new_file_path}\n"
                log_text.insert(tk.END, log_message)


def browse_directory():
    directory = filedialog.askdirectory()
    directory_entry.delete(0, tk.END)
    directory_entry.insert(0, directory)


def start_renaming():
    directory = directory_entry.get()
    old_name_pattern = old_name_entry.get()
    new_name = new_name_entry.get()

    rename_files_recursively(directory, old_name_pattern, new_name)


app = tk.Tk()
app.title("File Renamer")

directory_label = tk.Label(app, text="Directory:")
directory_label.grid(row=0, column=0, sticky="e")

directory_entry = tk.Entry(app, width=40)
directory_entry.grid(row=0, column=1)

browse_button = tk.Button(app, text="Browse", command=browse_directory)
browse_button.grid(row=0, column=2)

old_name_label = tk.Label(app, text="Old file name pattern:")
old_name_label.grid(row=1, column=0, sticky="e")

old_name_entry = tk.Entry(app, width=40)
old_name_entry.grid(row=1, column=1)

new_name_label = tk.Label(app, text="New file name:")
new_name_label.grid(row=2, column=0, sticky="e")

new_name_entry = tk.Entry(app, width=40)
new_name_entry.grid(row=2, column=1)

start_button = tk.Button(app, text="Start Renaming", command=start_renaming)
start_button.grid(row=3, column=1, pady=10)

log_label = tk.Label(app, text="Log:")
log_label.grid(row=4, column=0, sticky="nw")

log_text = tk.Text(app, wrap=tk.WORD, width=60, height=10)
log_text.grid(row=5, column=0, columnspan=3)

app.mainloop()
