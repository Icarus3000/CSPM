import json
import os

repo_path = r'c:\Projects\__CSPM'
log_path = r'C:\Users\CorySchneider\.gemini\antigravity\brain\4f123d7e-0be6-458e-b804-dcf780a3b33a\.system_generated\logs\transcript_full.jsonl'
qml_path = os.path.join(repo_path, r'src\qml\views\AccountsPayableView.qml')

# Start with the baseline file
os.system(f'git checkout 2e1262b -- "{qml_path}"')

with open(qml_path, 'r', encoding='utf-8') as f:
    content = f.read()

def apply_edit(content, tc):
    args = tc.get('args', {})
    if tc['name'] == 'replace_file_content':
        target = args.get('TargetContent', '')
        replacement = args.get('ReplacementContent', '')
        if target in content:
            content = content.replace(target, replacement, 1)
        else:
            print("Target not found for replace_file_content!")
    elif tc['name'] == 'multi_replace_file_content':
        chunks = args.get('ReplacementChunks', [])
        for chunk in chunks:
            target = chunk.get('TargetContent', '')
            replacement = chunk.get('ReplacementContent', '')
            if target in content:
                content = content.replace(target, replacement, 1)
            else:
                print("Target not found for multi_replace_file_content chunk!")
    return content

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if 'tool_calls' in data:
                for tc in data['tool_calls']:
                    if tc['name'] in ('replace_file_content', 'multi_replace_file_content'):
                        args = tc.get('args', {})
                        target_file = args.get('TargetFile', '')
                        if 'AccountsPayableView.qml' in target_file:
                            print(f"Applying edit from step {data.get('step_index')}")
                            content = apply_edit(content, tc)
        except Exception as e:
            pass

with open(qml_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Reconstruction complete.")
