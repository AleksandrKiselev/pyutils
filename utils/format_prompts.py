import re
import unicodedata
import random
from fuzzywuzzy import fuzz


def format_line(line, apply_mixed_case_conversion):
    line = re.sub(r',\s*$', '', line.strip())
    line = re.sub(r',(\S)', r', \1', line)

    def to_lower_if_mixed(word):
        if any(c.islower() for c in word) and any(c.isupper() for word in line.split() for c in word):
            return word.lower()
        return word

    if apply_mixed_case_conversion:
        line = ' '.join(to_lower_if_mixed(word) for word in line.split())
    return line


def filter_similar_lines(lines, similarity_threshold):
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


def normalize(text):
    text = unicodedata.normalize("NFKC", text.lower())
    text = text.strip(' \t\n"\'')

    # Замены символов
    text = text.replace("-", " ").replace("_", " ")
    text = text.replace("’", "'").replace("`", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("…", "...")

    # Удаление лишней пунктуации
    text = re.sub(r"[.!?;:(){}\[\]]", " ", text)

    # Приведение пробелов к одному
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def cluster_lines_by_similarity(lines, threshold):
    clusters = []
    unassigned = set(lines)

    while unassigned:
        line = unassigned.pop()

        # 1. Найти лучшую строку вне кластеров
        best_match = None
        best_match_score = 0
        for other in unassigned:
            score = fuzz.token_set_ratio(normalize(line), normalize(other))
            if score > best_match_score:
                best_match = other
                best_match_score = score

        # 2. Найти лучший кластер
        best_cluster = None
        best_cluster_score = 0
        for cluster in clusters:
            score = sum(fuzz.token_set_ratio(normalize(line), normalize(other)) for other in cluster) / len(cluster)
            if score > best_cluster_score:
                best_cluster = cluster
                best_cluster_score = score

        # 3. Сравниваем
        if best_match and best_match_score >= threshold and best_match_score > best_cluster_score:
            # Создаём новый кластер из двух строк
            unassigned.remove(best_match)
            clusters.append([line, best_match])
        elif best_cluster and best_cluster_score >= threshold:
            best_cluster.append(line)
        else:
            clusters.append([line])

    return clusters


def summarize_cluster(cluster):
    if not cluster:
        return "Empty cluster"

    avg_similarity = 100.0
    common_tokens = []

    # Средняя симиларити внутри кластера
    if len(cluster) > 1:
        # Разбиение каждой строки на токены (по запятым)
        token_lists = [set(re.split(r'[\s,]+', line.strip())) for line in cluster]
        common_tokens = set.intersection(*token_lists)
        similarities = []
        for i in range(len(cluster)):
            for j in range(i + 1, len(cluster)):
                sim = fuzz.token_set_ratio(cluster[i], cluster[j])
                similarities.append(sim)
        avg_similarity = round(sum(similarities) / len(similarities), 1)

    tokens_summary = ', '.join(sorted(common_tokens))
    return (f"\n\n# Cluster: [{tokens_summary}]  —  Avg similarity: {avg_similarity}%"
            f"\n##########################################################################")

def extract_tokens(line):
    norm_line = normalize(line)
    return set(t.strip().lower() for t in norm_line.split(",") if t)

def fuzzy_tag_match(token, tag_set, threshold=85):
    for tag in tag_set:
        if tag in token:
            return tag
        if fuzz.ratio(token, tag) >= threshold:
            return tag
    return None

def get_tag_groups(line, key_tag_clusters, threshold=95):
    tokens = extract_tokens(line)
    matched_groups = set()

    for group_name, tags in key_tag_clusters.items():
        for token in tokens:
            if fuzzy_tag_match(token, tags, threshold):
                matched_groups.add(group_name)
                break  # не нужно искать дальше внутри этой группы

    return matched_groups


def group_lines_by_tag(lines, key_tag_clusters, threshold=85):
    grouped = {}
    ungrouped = []

    for line in lines:
        groups = get_tag_groups(line, key_tag_clusters, threshold)
        if groups:
            key = ' + '.join(sorted(groups))
            grouped.setdefault(key, []).append(line)
        else:
            ungrouped.append(line)

    return grouped, ungrouped



def summarize_group(group, group_name="unnamed group"):
    if not group:
        return f"\n\n# Group: [{group_name}]\n##########################################################################"

    # Извлекаем общие токены, как в summarize_cluster
    token_lists = [set(token.strip() for token in normalize(line).split(',')) for line in group]
    common_tokens = set.intersection(*token_lists)

    tokens_summary = ', '.join(sorted(common_tokens)) if common_tokens else 'no common tokens'
    return (f"\n\n# Group: [{group_name}]  —  Common tokens: {tokens_summary}"
            f"\n##########################################################################")


key_tag_groups = {
    'presenting': {'solo'},
    'foreplay': {'buttjob', 'handjob', 'paizuri', 'titfuck', 'boobjob'},
    'blowjob': {'blowjob', 'deepthroat', 'fellatio', 'oral'},
    'missionary': {'missionary'},
    'cowgirl': {'cowgirl', 'riding'},
    'doggystyle': {'doggystyle'},
    'group sex': {'2boys', '3boys', '4boys', '2males', '3males', '4males', 'gangbang', 'multiple male', 'multiple boy',
                  'multiple cock', 'multiple penis', '2penis', '3penis',
                  'threesome', 'group sex', 'spitroast', 'double penetration'},
}


def process_file(file_path,
                 filter_similarity_threshold=90,
                 sort_by_similarity=False,
                 sort_by_tags=False,
                 sort_by_prompt=True,
                 random_sort=False,
                 cluster_similarity_threshold=80,
                 add_empty_lines = False,
                 apply_mixed_case_conversion=False):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = [format_line(line, apply_mixed_case_conversion) for line in file.readlines()]
        lines = filter_similar_lines(lines, filter_similarity_threshold)

        if sort_by_similarity:
            clusters = cluster_lines_by_similarity(lines, cluster_similarity_threshold)
            # Сортировка внутри каждого кластера по длине (можно заменить на алфавит)
            lines = []
            for cluster in clusters:
                cluster.sort(key=lambda x: x.lower())
            # Объединение кластеров в итоговый список
            for cluster in clusters:
                lines.append(summarize_cluster(cluster))
                lines.extend(cluster)
            formatted_lines = [line for line in lines if line.strip()]

        elif sort_by_tags:
            grouped, ungrouped = group_lines_by_tag(lines, key_tag_groups)
            lines = []

            # Обработка групп по комбинациям тегов
            for group_name in sorted(grouped):
                group = grouped[group_name]
                group.sort(key=lambda x: x.lower())
                lines.append(summarize_group(group, group_name))
                lines.extend(group)

            if ungrouped:
                ungrouped.sort(key=lambda x: x.lower())
                lines.append(summarize_group(ungrouped, "uncategorized"))
                lines.extend(ungrouped)
            formatted_lines = [line for line in lines if line.strip()]

        elif sort_by_prompt:
            lines.sort(key=lambda x: x.lower())
            formatted_lines = [line for line in lines if line.strip()]
        elif random_sort:
            lines = random.sample(lines, k=len(lines))
            formatted_lines = [line for line in lines if line.strip()]
        else:
            formatted_lines = [line for line in lines if line.strip()]

        if add_empty_lines:
            lines = formatted_lines
            formatted_lines = []
            for line in lines:
                if line.strip():
                    formatted_lines.append(line)
                    formatted_lines.append('')

    with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(formatted_lines))


file_path = r'D:\AI-Software\configs\wildcards\prompt\prompt.txt'
process_file(file_path)
