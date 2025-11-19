# backend/services/calendar_utils.py
"""
# 日历工具:生成 ICS 日历文件
"""
from pathlib import Path
from datetime import datetime, timedelta
import uuid
import re


def escape_ics_text(text: str) -> str:
    """转义 ICS 文本中的特殊字符"""
    text = text.replace('\\', '\\\\')
    text = text.replace(',', '\\,')
    text = text.replace(';', '\\;')
    text = text.replace('\n', '\\n')
    return text


def create_ics_file(
    title: str,
    start_time: str,
    organizer: str,
    attendee: str,
    duration_minutes: int = 45
) -> str:
    """
#     创建 ICS 日历文件
    
    Args:
#         title: 事件标题
#         start_time: 开始时间,格式:"2025-11-15 14:00, Asia/Shanghai" 或 "2025-11-15 14:00"
#         organizer: 组织者邮箱
#         attendee: 参与者邮箱
#         duration_minutes: 持续时间(分钟),默认45分钟
    
    Returns:
#         ICS 文件路径
    """
    # 解析时间字符串
    # 支持格式:"2025-11-15 14:00, Asia/Shanghai" 或 "2025-11-15 14:00"
    time_str = start_time.split(',')[0].strip()
    
    try:
        # 尝试解析时间
        start_dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        # 如果解析失败,尝试其他格式
        try:
            start_dt = datetime.strptime(time_str, "%Y/%m/%d %H:%M")
        except ValueError:
            # 如果还是失败,使用当前时间+1天
            start_dt = datetime.now() + timedelta(days=1)
            start_dt = start_dt.replace(hour=14, minute=0, second=0, microsecond=0)
    
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    
    # 生成唯一ID
    uid = str(uuid.uuid4())
    
    # 格式化时间为 ICS 格式(UTC)
    # ICS 格式要求:YYYYMMDDTHHMMSSZ
    dtstart_str = start_dt.strftime('%Y%m%dT%H%M%S')
    dtend_str = end_dt.strftime('%Y%m%dT%H%M%S')
    dtstamp_str = datetime.now().strftime('%Y%m%dT%H%M%S')
    
    # 转义特殊字符
    title_escaped = escape_ics_text(title)
    organizer_escaped = escape_ics_text(organizer)
    attendee_escaped = escape_ics_text(attendee)
    
    # 生成 ICS 内容
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//RecruitFlow//CN
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp_str}
DTSTART:{dtstart_str}
DTEND:{dtend_str}
SUMMARY:{title_escaped}
# DESCRIPTION:自动生成的面试邀约
ORGANIZER;CN=HR Team:MAILTO:{organizer_escaped}
ATTENDEE;CN=Candidate;RSVP=TRUE:MAILTO:{attendee_escaped}
STATUS:CONFIRMED
SEQUENCE:0
END:VEVENT
END:VCALENDAR
"""
    
    # 确保输出目录存在
    out_dir = Path("reports/invites")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存文件
    ics_path = out_dir / f"invite_{uid}.ics"
    ics_path.write_text(ics_content, encoding="utf-8")
    
    return str(ics_path)

    
    try:
        # 尝试解析时间
        start_dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        # 如果解析失败,尝试其他格式
        try:
            start_dt = datetime.strptime(time_str, "%Y/%m/%d %H:%M")
        except ValueError:
            # 如果还是失败,使用当前时间+1天
            start_dt = datetime.now() + timedelta(days=1)
            start_dt = start_dt.replace(hour=14, minute=0, second=0, microsecond=0)
    
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    
    # 生成唯一ID
    uid = str(uuid.uuid4())
    
    # 格式化时间为 ICS 格式(UTC)
    # ICS 格式要求:YYYYMMDDTHHMMSSZ
    dtstart_str = start_dt.strftime('%Y%m%dT%H%M%S')
    dtend_str = end_dt.strftime('%Y%m%dT%H%M%S')
    dtstamp_str = datetime.now().strftime('%Y%m%dT%H%M%S')
    
    # 转义特殊字符
    title_escaped = escape_ics_text(title)
    organizer_escaped = escape_ics_text(organizer)
    attendee_escaped = escape_ics_text(attendee)
    
    # 生成 ICS 内容
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//RecruitFlow//CN
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp_str}
DTSTART:{dtstart_str}
DTEND:{dtend_str}
SUMMARY:{title_escaped}
# DESCRIPTION:自动生成的面试邀约
ORGANIZER;CN=HR Team:MAILTO:{organizer_escaped}
ATTENDEE;CN=Candidate;RSVP=TRUE:MAILTO:{attendee_escaped}
STATUS:CONFIRMED
SEQUENCE:0
END:VEVENT
END:VCALENDAR
"""
    
    # 确保输出目录存在
    out_dir = Path("reports/invites")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存文件
    ics_path = out_dir / f"invite_{uid}.ics"
    ics_path.write_text(ics_content, encoding="utf-8")
    
    return str(ics_path)
