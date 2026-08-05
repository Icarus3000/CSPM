import json
from pathlib import Path
from collections import Counter

manifest_path = Path(r"c:\Users\cschn\Documents\LIH (Personal)\OneDrive - Lawyers in House\__CSPM\dumps\chatpack\2026-03-17_071919_premultimondragfix\03_MANIFEST.json")
obj = json.loads(manifest_path.read_text(encoding='utf-8'))
print('total entries', len(obj))

cnt = Counter([x['path'].split('\\')[0] for x in obj])
print('top dirs', cnt.most_common(12))
print('unique top segments', len(cnt))

# show some excluded candidates
groups = {k:v for k,v in cnt.items() if k.startswith('.')}
print('dot dirs', {k:v for k,v in groups.items() if v>0})
