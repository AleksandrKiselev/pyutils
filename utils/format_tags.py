def format_tags(file):
    try:
        with open(file, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
        result = ', '.join(line.strip().lower() for line in lines if line.strip())
        with open(file, 'w', encoding='utf-8') as f:
            f.write(result)

        print(f"Преобразование завершено. Результат сохранён в {file}")

    except FileNotFoundError:
        print(f"Файл {file} не найден.")
    except Exception as e:
        print(f"Произошла ошибка: {e}")



file = r'D:\AI-Software\configs\wildcards\llm.txt'
format_tags(file)
