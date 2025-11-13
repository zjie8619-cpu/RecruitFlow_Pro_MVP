import json, uuid, datetime as dt
from backend.storage.db import get_db

def audit_log(action: str, payload: dict, actor: str = "system") -> None:
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO audit (id, ts, actor, action, payload) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), dt.datetime.utcnow().isoformat(), actor, action, json.dumps(payload, ensure_ascii=False))
    )
    conn.commit(); conn.close()

