import json

transcript_path = r"C:\Users\cschn\.gemini\antigravity\brain\ed2a86cb-00a6-47ca-bbb2-4eb3858f1d78\.system_generated\logs\transcript_full.jsonl"
out_path = r"c:\Projects\__CSPM\extract.txt"

matches = []
with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        if "def createDraftWithGrouping" in line:
            data = json.loads(line)
            if "content" in data:
                matches.append(data["content"])
            if "tool_calls" in data:
                for tc in data["tool_calls"]:
                    matches.append(str(tc))

with open(out_path, "w", encoding="utf-8") as f:
    for match in matches:
        f.write(match)
        f.write("\n" + "="*80 + "\n")

print(f"Extracted to {out_path}")
