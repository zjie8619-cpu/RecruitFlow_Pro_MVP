import re
from typing import Dict

def parse_text_resume(txt: str) -> Dict:
    email = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", txt)
    phone = re.search(r"(1[3-9]\d{9})", txt)
    years = re.search(r"(\d+)\s年", txt)
    name = re.search(r"姓名[:：]\s([^\n\r\s]+)", txt)
    edu = re.search(r"(本科|大专|硕士|研究生|博士)", txt)
    return {
        "name": name.group(1) if name else "",
        "email": email.group(0) if email else "",
        "phone": phone.group(1) if phone else "",
        "years": float(years.group(1)) if years else 0.0,
        "edu": edu.group(1) if edu else "",
        "text_raw": txt
    }

