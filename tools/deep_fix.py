import os
import ast

TARGET = "backend"


def check_syntax(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        ast.parse(code)
        return None
    except Exception as e:
        return str(e)


def walk_and_check():
    errors = []
    for root, dirs, files in os.walk(TARGET):
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(root, f)
                err = check_syntax(p)
                if err:
                    errors.append((p, err))
    return errors


def auto_fix_line_errors(path, error_msg):
    fixed = []
    changed = False

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        clean = line

        if "invalid character" in error_msg:
            clean = clean.encode("ascii", "ignore").decode()
            changed = True

        if "unexpected indent" in error_msg:
            clean = clean.lstrip()
            changed = True

        fixed.append(clean)

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(fixed)
        print(f"[FIXED] {path}")
    else:
        print(f"[SKIP] no change: {path}")


def run_fix():
    print("=== Scan syntax errors ===")
    errors = walk_and_check()

    if not errors:
        print("All Python files passed syntax check.")
        return

    print(f"Found {len(errors)} syntax errors, attempting auto-fix...\n")

    for path, msg in errors:
        print(f"Fixing: {path}")
        auto_fix_line_errors(path, msg)

    print("\n=== Done. Please re-run ===")
    print("python -m py_compile backend/**/**/*.py")


if __name__ == "__main__":
    run_fix()



TARGET = "backend"


def check_syntax(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        ast.parse(code)
        return None
    except Exception as e:
        return str(e)


def walk_and_check():
    errors = []
    for root, dirs, files in os.walk(TARGET):
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(root, f)
                err = check_syntax(p)
                if err:
                    errors.append((p, err))
    return errors


def auto_fix_line_errors(path, error_msg):
    fixed = []
    changed = False

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        clean = line

        if "invalid character" in error_msg:
            clean = clean.encode("ascii", "ignore").decode()
            changed = True

        if "unexpected indent" in error_msg:
            clean = clean.lstrip()
            changed = True

        fixed.append(clean)

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(fixed)
        print(f"[FIXED] {path}")
    else:
        print(f"[SKIP] no change: {path}")


def run_fix():
    print("=== Scan syntax errors ===")
    errors = walk_and_check()

    if not errors:
        print("All Python files passed syntax check.")
        return

    print(f"Found {len(errors)} syntax errors, attempting auto-fix...\n")

    for path, msg in errors:
        print(f"Fixing: {path}")
        auto_fix_line_errors(path, msg)

    print("\n=== Done. Please re-run ===")
    print("python -m py_compile backend/**/**/*.py")


if __name__ == "__main__":
    run_fix()



