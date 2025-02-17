import os
import json
import re


input_directory = r'g:\AI-Software\stable-diffusion-webui\models\Lora\test'
output_file = r'd:\AI-Software\configs\wildcards\lora\test.txt'


def process_prompt(prompt):
    processed = re.sub(r',\s*', ', ', prompt)
    processed = processed.rstrip()
    return processed


with open(output_file, 'w') as outfile:
    for filename in os.listdir(input_directory):
        if filename.endswith('.json'):
            file_path = os.path.join(input_directory, filename)
            with open(file_path, 'r', encoding='utf-8') as json_file:
                try:
                    data = json.load(json_file)
                    prompt = process_prompt(data.get('activation text', ''))
                    line = f"<lora:test\\{os.path.splitext(filename)[0]}:0.8> {prompt}\n"
                    outfile.write(line)
                except json.JSONDecodeError as e:
                    print(f"Error parsing {filename}: {e}")
                except Exception as e:
                    print(f"An error occurred with {filename}: {e}")

print("Processing completed. Check the output file.")
