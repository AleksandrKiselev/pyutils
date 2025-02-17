def load_lines(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())


def save_lines(filepath, lines):
    with open(filepath, 'w', encoding='utf-8') as f:
        for line in sorted(lines):
            f.write(line + '\n')


def main(file1, file2, output_file):
    lines1 = load_lines(file1)
    lines2 = load_lines(file2)
    unique_lines = (lines1 - lines2) | (lines2 - lines1)
    save_lines(output_file, unique_lines)

file1 = "d:\\AI-Software\\configs\\wildcards\\nsfw.txt"
file2 = "d:\\AI-Software\\configs\\wildcards\\nsfw_by_groups.txt"
file3 = "d:\\AI-Software\\configs\\wildcards\\nsfw_intersected.txt"
main(file1, file2, file3)
