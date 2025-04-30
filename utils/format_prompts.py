import re
from fuzzywuzzy import fuzz


def format_line(line, apply_mixed_case_conversion):
    line = re.sub(r',\s*$', '', line.strip())
    line = re.sub(r',(\S)', r', \1', line)

    def to_lower_if_mixed(word):
        if any(c.islower() for c in word) and any(c.isupper() for c in word):
            return word.lower()
        return word

    if apply_mixed_case_conversion:
        line = ' '.join(to_lower_if_mixed(word) for word in line.split())
    return line


def find_similar_lines(lines, similarity_threshold):
    unique_lines = []
    skip_indices = set()

    for i, line1 in enumerate(lines):
        if i in skip_indices:
            continue
        similar_group = [line1]
        for j, line2 in enumerate(lines[i + 1:], start=i + 1):
            if j in skip_indices:
                continue
            similarity = fuzz.ratio(line1, line2)
            if similarity >= similarity_threshold:
                similar_group.append(line2)
                skip_indices.add(j)

        longest_line = max(similar_group, key=len)
        unique_lines.append(longest_line)

        if len(similar_group) > 1:
            print("Similar lines group:")
            for line in similar_group:
                print(f"  - {line}")
            print(f"Kept line: {longest_line}\n")

    return unique_lines


def process_file(path, similarity_threshold, sort=False, add_empty_lines=True, apply_mixed_case_conversion=True):
    with open(path, 'r', encoding='utf-8') as file:
        lines = [format_line(line, apply_mixed_case_conversion) for line in file.readlines()]

        lines = find_similar_lines(lines, similarity_threshold)
        if sort:
            lines = sorted(lines, key=lambda x: x.lower())

        if add_empty_lines:
            formatted_lines = []
            for line in lines:
                if line.strip():
                    formatted_lines.append(line)
                    formatted_lines.append('')
        else:
            formatted_lines = [line for line in lines if line.strip()]

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(formatted_lines))


file_path = r'D:\AI-Software\configs\wildcards\char.txt'
process_file(file_path, similarity_threshold=95, sort=True, add_empty_lines=True, apply_mixed_case_conversion=True)