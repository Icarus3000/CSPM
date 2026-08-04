import json

log_path = r'C:\Users\CorySchneider\.gemini\antigravity\brain\4f123d7e-0be6-458e-b804-dcf780a3b33a\.system_generated\logs\transcript_full.jsonl'
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
                            if data.get('step_index') == 189:
                                print(f"Step 189 Replacement Content length: {len(args.get('ReplacementContent', ''))}")
                                # let's write it to a file so we can look at it
                                with open(r'c:\Projects\__CSPM\AccountsPayableView_step189.qml', 'w', encoding='utf-8') as out:
                                    out.write(args.get('ReplacementContent', ''))
        except:
            pass
