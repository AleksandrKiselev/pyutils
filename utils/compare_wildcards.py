# compare_prompts.py

def read_prompts(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())


def main():
    file1 = 'D:\\AI-Software\\configs\\wildcards\\nsfw\\4after.txt'
    file2 = 'D:\\AI-Software\\configs\\wildcards\\set\\nsfw.txt'

    prompts_a = read_prompts(file1)
    prompts_b = read_prompts(file2)

    only_in_a = prompts_a - prompts_b
    only_in_b = prompts_b - prompts_a

    print(f"🔹 Prompts in {file1} but not in {file2}:\n")
    for prompt in sorted(only_in_a):
        print(prompt)

    print(f"\n🔸 Prompts in {file2} but not in {file1}:\n")
    for prompt in sorted(only_in_b):
        print(prompt)


if __name__ == "__main__":
    main()