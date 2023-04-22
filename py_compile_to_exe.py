import os
import subprocess
import tkinter as tk
from tkinter import filedialog
import shutil


def browse_python_file():
    file_path = filedialog.askopenfilename(filetypes=[("Python files", "*.py")])
    python_file_entry.delete(0, tk.END)
    python_file_entry.insert(0, file_path)


def compile_to_exe():
    python_file_path = python_file_entry.get()
    output_folder = os.path.dirname(python_file_path)
    output_name = os.path.splitext(os.path.basename(python_file_path))[0]
    command = f"pyinstaller --noconsole --onefile --distpath {output_folder} --name {output_name} {python_file_path}"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()

    if process.returncode == 0:
        output_exe = os.path.join(output_folder, output_name + ".exe")
        output_message = f"Success: {output_exe} created\n"
        log_text.insert(tk.END, output_message)

        # Удаление папки build и файла .spec
        build_folder = os.path.join(os.getcwd(), "build")
        spec_file = os.path.join(os.getcwd(), output_name + ".spec")
        if os.path.exists(build_folder):
            shutil.rmtree(build_folder)
        if os.path.exists(spec_file):
            os.remove(spec_file)
    else:
        log_text.insert(tk.END, "Error:\n" + error.decode("utf-8") + "\n")


app = tk.Tk()
app.title("Python to EXE Compiler")

python_file_label = tk.Label(app, text="Python file:")
python_file_label.grid(row=0, column=0, sticky="e")

python_file_entry = tk.Entry(app, width=40)
python_file_entry.grid(row=0, column=1)

browse_button = tk.Button(app, text="Browse", command=browse_python_file)
browse_button.grid(row=0, column=2)

compile_button = tk.Button(app, text="Compile to EXE", command=compile_to_exe)
compile_button.grid(row=1, column=1, pady=10)

log_label = tk.Label(app, text="Log:")
log_label.grid(row=2, column=0, sticky="nw")

log_text = tk.Text(app, wrap=tk.WORD, width=60, height=10)
log_text.grid(row=3, column=0, columnspan=3)

app.mainloop()
