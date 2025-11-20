from pathlib import Path
from datetime import datetime, timedelta
import uuid

def make_invite_email(candidate: dict, job: str) -> str:
#     name = (candidate.get("name") or "候选人").strip() or "候选人"
    hi=[]
#     if candidate.get("skills"): hi.append(f"技能匹配:{candidate['skills'][:40]}")
#     if candidate.get("projects"): hi.append(f"项目亮点:{candidate['projects'][:40]}")
#     if candidate.get("years"): hi.append(f"相关年限:{candidate['years']} ?)
#     h = "?.join(hi[:2]) if hi else "匹配度良好,期待交流"
    return f"""Hi {name}?

# 我们是教育科技公司人力团队,关于「{job}」岗位想与您安排一?30-45 分钟的初步交流?
# 初步评估亮点:{h}

# 若您方便,请接受随信附带的日历邀请(.ics),届时我们在企业微?Zoom 见?

# 感谢?
HR Team
"""
def write_ics(title: str, start_time: str, duration_minutes: int, organizer: str, attendee_email: str) -> str:
    dt_str = start_time.split(',')[0].strip()
    start_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    uid = str(uuid.uuid4())
    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//RecruitFlow//CN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{start_dt.strftime('%Y%m%dT%H%M%S')}
DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}
DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}
SUMMARY:{title}
# DESCRIPTION:自动生成的面试邀?
ORGANIZER:MAILTO:{organizer}
ATTENDEE;CN=Candidate:MAILTO:{attendee_email}
END:VEVENT
END:VCALENDAR
"""
    out_dir = Path("reports/invites"); out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"invite_{uid}.ics"
    path.write_text(ics, encoding="utf-8")
    return str(path)

