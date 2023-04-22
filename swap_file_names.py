import os
import tkinter as tk
from tkinter import filedialog
from pathlib import Path


def browse_directory():
    folder_path = filedialog.askdirectory()
    directory_entry.delete(0, tk.END)
    directory_entry.insert(0, folder_path)


def swap_file_names():
    folder_path = directory_entry.get()
    file_name1 = file1_entry.get()
    file_name2 = file2_entry.get()
    log_text.delete(1.0, tk.END)

    for root, _, files in os.walk(folder_path):
        if file_name1 in files and file_name2 in files:
            file1 = os.path.join(root, file_name1)
            file2 = os.path.join(root, file_name2)
            temp_file = os.path.join(root, "temp" + Path(file1).suffix)

            os.rename(file1, temp_file)
            os.rename(file2, file1)
            os.rename(temp_file, file2)

            log_text.insert(tk.END, f"Swapped: {file1} <-> {file2}\n")


app = tk.Tk()
app.title("Swap File Names")

directory_label = tk.Label(app, text="Directory:")
directory_label.grid(row=0, column=0, sticky="e")

directory_entry = tk.Entry(app, width=40)
directory_entry.grid(row=0, column=1)

browse_button = tk.Button(app, text="Browse", command=browse_directory)
browse_button.grid(row=0, column=2)

file1_label = tk.Label(app, text="File 1:")
file1_label.grid(row=1, column=0, sticky="e")

file1_entry = tk.Entry(app, width=40)
file1_entry.grid(row=1, column=1)

file2_label = tk.Label(app, text="File 2:")
file2_label.grid(row=2, column=0, sticky="e")

file2_entry = tk.Entry(app, width=40)
file2_entry.grid(row=2, column=1)

swap_button = tk.Button(app, text="Swap File Names", command=swap_file_names)
swap_button.grid(row=3, column=1, pady=10)

log_label = tk.Label(app, text="Log:")
log_label.grid(row=4, column=0, sticky="nw")

log_text = tk.Text(app, wrap=tk.WORD, width=60, height=10)
log_text.grid(row=5, column=0, columnspan=3)

app.mainloop()
