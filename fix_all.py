import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def run(cmd: str):
    """Run a shell command and exit if it fails."""
    print("\n>>", cmd)
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print("\n!! Command failed, please check the error above.")
        input("Press Enter to exit...")
        sys.exit(1)


def write_ai_client():
    """Overwrite backend/services/ai_client.py to use SiliconFlow via openai client."""
    code = '''import os
import openai


def get_client_and_cfg():
    client = openai.OpenAI(
        api_key=os.getenv("SILICON_API_KEY"),
        base_url="https://api.siliconflow.cn/v1/"
    )
    cfg = {
        "model": "deepseek-ai/DeepSeek-V3",
        "temperature": 0.3,
    }
    return client, cfg
'''
    path = ROOT / "backend" / "services" / "ai_client.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")
    print("-> backend/services/ai_client.py written.")


def main():
    print("=== RecruitFlow AUTO FIX (Python 3.13) ===")

    # 1. Ensure pip exists and is up to date
    run(f'"{PY}" -m ensurepip')
    run(f'"{PY}" -m pip install --upgrade pip')

    # 2. Clean old openai
    run(f'"{PY}" -m pip uninstall -y openai')

    # 3. Install needed packages (compatible with 3.13)
    run(f'"{PY}" -m pip install openai streamlit requests pandas')

    # 4. Fix ai_client to use SiliconFlow
    write_ai_client()

    # 5. Start Streamlit app
    print("\n=== Starting Streamlit ===")
    run(f'"{PY}" -m streamlit run app/streamlit_app.py')


if __name__ == "__main__":
    main()