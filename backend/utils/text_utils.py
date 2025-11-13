import re
from typing import List

def normalize(s: str) -> str:
    s = (s or "").lower().strip()
    return re.sub(r"\s+"," ", s)

def contains_any(text: str, keywords: List[str]) -> List[str]:
    t = normalize(text)
    hits = []
    for kw in [k for k in keywords if k]:
        if kw.lower().strip() in t:
            hits.append(kw)
    return hits

