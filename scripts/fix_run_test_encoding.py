from pathlib import Path

path = Path("backend/run_test.py")
text = path.read_text(encoding="utf-16")
path.write_text(text, encoding="utf-8")
print("converted backend/run_test.py to utf-8")
