import os
import re

ROOT = "backend"

REPLACE_MAP = {
    "【": "[",
    "】": "]",
    "（": "(",
    "）": ")",
    "，": ",",
    "。": ".",
    "：": ":",
    "；": ";",
    "！": "!",
    "？": "?",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "\t": "    ",
}

SAFE_LINE = ["# ", "'''", '"""']


def fix_file(path):
    fixed_lines = []
    changed = False

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for line in lines:
        clean = line.replace("\ufeff", "")

        for k, v in REPLACE_MAP.items():
            if k in clean:
                clean = clean.replace(k, v)
                changed = True

        if re.search(r"[\u4e00-\u9fa5]+", clean):
            striped = clean.strip()
            if not any(striped.startswith(s) for s in SAFE_LINE):
                clean = "# " + clean
                changed = True

        fixed_lines.append(clean)

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(fixed_lines)
        print(f"[FIXED] {path}")


def walk_and_fix():
    print("=== Start scanning backend/ Python files ===")

    for root, dirs, files in os.walk(ROOT):
        for file in files:
            if file.endswith(".py"):
                fix_file(os.path.join(root, file))

    print("\nAll fixes applied. Run: python -m py_compile backend/**/**/*.py\n")


if __name__ == "__main__":
    walk_and_fix()



ROOT = "backend"

REPLACE_MAP = {
    "【": "[",
    "】": "]",
    "（": "(",
    "）": ")",
    "，": ",",
    "。": ".",
    "：": ":",
    "；": ";",
    "！": "!",
    "？": "?",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "\t": "    ",
}

SAFE_LINE = ["# ", "'''", '"""']


def fix_file(path):
    fixed_lines = []
    changed = False

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for line in lines:
        clean = line.replace("\ufeff", "")

        for k, v in REPLACE_MAP.items():
            if k in clean:
                clean = clean.replace(k, v)
                changed = True

        if re.search(r"[\u4e00-\u9fa5]+", clean):
            striped = clean.strip()
            if not any(striped.startswith(s) for s in SAFE_LINE):
                clean = "# " + clean
                changed = True

        fixed_lines.append(clean)

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(fixed_lines)
        print(f"[FIXED] {path}")


def walk_and_fix():
    print("=== Start scanning backend/ Python files ===")

    for root, dirs, files in os.walk(ROOT):
        for file in files:
            if file.endswith(".py"):
                fix_file(os.path.join(root, file))

    print("\nAll fixes applied. Run: python -m py_compile backend/**/**/*.py\n")


if __name__ == "__main__":
    walk_and_fix()



