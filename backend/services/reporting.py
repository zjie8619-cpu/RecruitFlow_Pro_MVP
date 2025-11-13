import pandas as pd
from pathlib import Path
from datetime import datetime

def export_round_report(scored_df: pd.DataFrame) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("reports"); out_dir.mkdir(exist_ok=True, parents=True)
    csv_path = out_dir / f"recruit_round_{ts}.csv"
    xlsx_path = out_dir / f"recruit_round_{ts}.xlsx"
    df = scored_df.copy()
    def mask_phone(x: str):
        x = str(x); return x[:3]+"****"+x[-4:] if len(x)>=7 else x
    if "phone" in df.columns: df["phone_masked"] = df["phone"].apply(mask_phone)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    try:
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="candidates")
    except Exception:
        pass
    return str(csv_path)

