def add_text_to_lines(file, prefix, suffix):
    with open(file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    with open(file, 'w', encoding='utf-8') as f:
        for line in lines:
            line = line.strip()
            if len(line) > 0:
                line = f"{prefix}, {line}, {suffix}\n"
            else:
                line = "\n"
            f.write(line)


file = r'D:\AI-Software\configs\wildcards\raw_char.txt'
prefix = '1girl'
suffix = 'thin waist, wide hips, round ass, curvy body, slender'
add_text_to_lines(file, prefix, suffix)