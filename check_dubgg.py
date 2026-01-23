import tempfile
import os
from src.utils.archive_utils import ArchiveExtractor

# Extract dubgg from dubgg.sz
td = tempfile.mkdtemp()
path = ArchiveExtractor.extract_file('dubgg.sz', 'dubgg', td)
print(f'Extracted to: {path}')
print(f'File exists: {os.path.exists(path)}')
print(f'File size: {os.path.getsize(path)} bytes')

# Check content
with open(path, 'rb') as f:
    header = f.read(200)
    print(f'First 200 bytes (hex): {header[:50].hex()}')
    print(f'First 200 bytes (text): {header[:200]}')
    
# Try as text
try:
    with open(path, 'r', encoding='utf-8') as f:
        first_lines = f.read(500)
        print(f'\nFirst 500 chars as UTF-8:\n{first_lines}')
except:
    print('Not readable as UTF-8')
