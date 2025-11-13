import os
from datetime import datetime, timedelta

import pytz


def create_ics_file(title: str, start_time: str, organizer: str, attendee: str) -> str:
    """生成 ICS 文件供候选人添加到日历"""
    ics_dir = "reports/invites"
    os.makedirs(ics_dir, exist_ok=True)

    try:
        time_part, tz_part = [x.strip() for x in start_time.split(",", 1)]
    except ValueError:
        raise ValueError("面试时间格式应为：YYYY-MM-DD HH:MM, 时区  例如：2025-11-15 14:00, Asia/Shanghai")

    start_dt = datetime.strptime(time_part, "%Y-%m-%d %H:%M")
    tz = pytz.timezone(tz_part)
    start_local = tz.localize(start_dt)
    end_local = start_local + timedelta(minutes=45)

    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//RecruitFlow AI//面试邀请//CN
BEGIN:VEVENT
SUMMARY:{title}
DTSTART;TZID={tz_part}:{start_local.strftime("%Y%m%dT%H%M%S")}
DTEND;TZID={tz_part}:{end_local.strftime("%Y%m%dT%H%M%S")}
ORGANIZER;CN=HR Team:MAILTO:{organizer}
ATTENDEE;CN={attendee}:MAILTO:{attendee}
DESCRIPTION:诚邀您参加本次面试！
END:VEVENT
END:VCALENDAR
"""

    file_path = os.path.join(ics_dir, f"invite_{abs(hash(title + attendee)) & 0xfffffff}.ics")
    with open(file_path, "w", encoding="utf-8") as fp:
        fp.write(ics_content)

    return file_path

