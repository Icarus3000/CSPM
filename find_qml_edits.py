import json

log_path = r'C:\Users\CorySchneider\.gemini\antigravity\brain\4f123d7e-0be6-458e-b804-dcf780a3b33a\.system_generated\logs\transcript_full.jsonl'
try:
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                if 'tool_calls' in data:
                    for tc in data['tool_calls']:
                        if tc['name'] in ('replace_file_content', 'multi_replace_file_content'):
                            args = tc.get('args', {})
                            target = args.get('TargetFile', '')
                            if 'AccountsPayableView.qml' in target:
                                print(f"Found {tc['name']} at step {data.get('step_index')}")
            except Exception as e:
                print(f"Error parsing line: {e}")
except Exception as e:
    print(f"Error opening file: {e}")
