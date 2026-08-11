from pathlib import Path
from collections import Counter
import re

path = Path('mypy_diagnostic.txt')
if not path.exists():
    raise SystemExit('mypy_diagnostic.txt not found')
lines = path.read_text(encoding='utf-8').splitlines()
errors = []
for line in lines:
    if not line.strip():
        continue
    if line.startswith('pyproject.toml: note:'):
        continue
    if 'Found ' in line and 'errors in ' in line:
        continue
    parts = line.split(':', 4)
    if len(parts) < 5:
        continue
    file = parts[0]
    rest = parts[4]
    if '[' in rest and ']' in rest:
        errcode = rest.split('[')[-1].rstrip(']')
        msg = rest.split('[')[0].strip()
    else:
        errcode = 'UNKNOWN'
        msg = rest.strip()
    errors.append((file, errcode, msg))

by_code = Counter(e[1] for e in errors)
by_file = Counter(e[0] for e in errors)
print('TOTAL_ERRORS', len(errors))
print('UNIQUE_FILES', len(by_file))
print('\nTOP ERROR CODES:')
for code, count in by_code.most_common(10):
    print(f'{code}: {count}')
print('\nTOP FILES:')
for file, count in by_file.most_common(10):
    print(f'{count}: {file}')
print('\nERRORS IN TEST FILES:')
for file, count in sorted(by_file.items(), key=lambda x: x[1], reverse=True):
    if file.startswith('backend/tests/'):
        print(f'{count}: {file}')
print('\nNOTES:')
for line in lines:
    if line.startswith('pyproject.toml: note:'):
        print(line)
