import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable

def run(cmd):
    print("\n>>>", cmd)
    p = subprocess.run(cmd, shell=True)
    if p.returncode != 0:
        print("\n!!! Command failed:", cmd)
        sys.exit(1)

def replace_text(file, old, new):
    f = ROOT / file
    if f.exists():
        txt = f.read_text(encoding="utf-8")
        if old in txt:
            txt = txt.replace(old, new)
            f.write_text(txt, encoding="utf-8")
            print("Fixed:", file)

def main():
    print("\n=== RecruitFlow Auto Fix Tool ===\n")

    # 1. ensure pip works
    run(f"{PY} -m ensurepip")
    run(f"{PY} -m pip install --upgrade pip")

    # 2. uninstall old openai package
    run(f"{PY} -m pip uninstall -y openai")

    # 3. install siliconcloud sdk
    run(f"{PY} -m pip install siliconcloud")

    # 4. fix import statements in project code
    replace_text("backend/services/ai_client.py", "from openai import OpenAI", "from siliconcloud import SiliconCloud")
    replace_text("backend/services/ai_client.py", "OpenAI(", "SiliconCloud(")

    replace_text("backend/services/ai_core.py", "OpenAI", "SiliconCloud")
    replace_text("backend/services/jd_ai.py", "OpenAI", "SiliconCloud")

    # 5. install dependencies
    req = ROOT / "requirements.txt"
    if req.exists():
        run(f"{PY} -m pip install -r requirements.txt")
    else:
        print("requirements.txt not found, skipping")

    # 6. start streamlit
    print("\n=== Starting Streamlit ===\n")
    run(f"{PY} -m streamlit run app/streamlit_app.py")

if __name__ == "__main__":
    main()
