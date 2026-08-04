import os
import zlib

def parse_tree(blob):
    entries = []
    rest = blob
    while rest:
        nul_idx = rest.find(b'\0')
        if nul_idx == -1: break
        mode_name = rest[:nul_idx]
        mode, name = mode_name.split(b' ', 1)
        sha = rest[nul_idx+1:nul_idx+21]
        entries.append((mode, name.decode('utf-8'), sha.hex()))
        rest = rest[nul_idx+21:]
    return entries

def read_object(sha):
    path = os.path.join('.git', 'objects', sha[:2], sha[2:])
    with open(path, 'rb') as f:
        data = zlib.decompress(f.read())
    obj_type, rest = data.split(b' ', 1)
    size, content = rest.split(b'\0', 1)
    return obj_type.decode('utf-8'), content

def get_tree_from_commit(sha):
    _, content = read_object(sha)
    lines = content.split(b'\n')
    for line in lines:
        if line.startswith(b'tree '):
            return line.split(b' ')[1].decode('utf-8')
    return None

with open('.git/HEAD', 'r') as f:
    ref = f.read().strip().split(' ')[1]
with open('.git/' + ref, 'r') as f:
    commit_sha = f.read().strip()

tree_sha = get_tree_from_commit(commit_sha)
def find_file(tree_sha, path_parts):
    _, content = read_object(tree_sha)
    entries = parse_tree(content)
    for mode, name, sha in entries:
        if name == path_parts[0]:
            if len(path_parts) == 1:
                return sha
            else:
                return find_file(sha, path_parts[1:])
    return None

file_sha = find_file(tree_sha, ['src', 'python', 'domain', 'schema_constants.py'])
if file_sha:
    _, file_content = read_object(file_sha)
    with open('src/python/domain/schema_constants.py', 'wb') as f:
        f.write(file_content)
    print("RESTORED SUCCESSFULLY")
else:
    print("FILE NOT FOUND IN GIT")
