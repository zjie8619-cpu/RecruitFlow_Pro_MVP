# backend/services/calendar_utils.py
"""
日历工具:生成 ICS 日历文件 (符合 RFC 5545 标准)
"""
from pathlib import Path
from datetime import datetime, timedelta
import uuid
import re
import random
import string


def escape_ics_text(text: str) -> str:
    """转义 ICS 文本中的特殊字符（RFC 5545）"""
    if not text:
        return ""
    # 先替换英文逗号为中文逗号（符合用户要求：DESCRIPTION中不得包含英文逗号）
    text = text.replace(',', '，')
    # 转义特殊字符（RFC 5545要求）
    text = text.replace('\\', '\\\\')  # 必须先转义反斜杠
    text = text.replace(';', '\\;')
    text = text.replace('\n', '\\n')
    # 注意：中文逗号不需要转义，只有ASCII逗号需要转义为\,，但我们已经替换为中文逗号了
    return text


def generate_random_string(length: int = 6) -> str:
    """生成随机字符串"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def create_ics_file(
    title: str,
    start_time: str,
    organizer: str,
    attendee: str,
    duration_minutes: int = 45,
    location: str = "",
    description: str = ""
) -> str:
    """
    创建 ICS 日历文件（符合 RFC 5545 标准）
    
    Args:
        title: 事件标题（SUMMARY）
        start_time: 开始时间,格式:"2025-11-15 14:00, Asia/Shanghai" 或 "2025-11-15 14:00"
        organizer: 组织者邮箱
        attendee: 参与者邮箱
        duration_minutes: 持续时间(分钟),默认45分钟
        location: 地点（LOCATION）
        description: 详细说明（DESCRIPTION）
    
    Returns:
        ICS 文件路径
    """
    # 解析时间字符串
    # 支持格式:"2025-11-15 14:00, Asia/Shanghai" 或 "2025-11-15 14:00"
    parts = start_time.split(',')
    time_str = parts[0].strip()
    timezone_str = parts[1].strip() if len(parts) > 1 else "Asia/Shanghai"
    
    try:
        # 解析本地时间
        start_dt_local = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            start_dt_local = datetime.strptime(time_str, "%Y/%m/%d %H:%M")
        except ValueError:
            # 如果解析失败,使用当前时间+1天
            start_dt_local = datetime.now() + timedelta(days=1)
            start_dt_local = start_dt_local.replace(hour=14, minute=0, second=0, microsecond=0)
    
    # 计算结束时间（本地时间）
    end_dt_local = start_dt_local + timedelta(minutes=duration_minutes)
    
    # 生成 UID（按照要求：开始时间 + "-" + 随机6位字符串 + "@interview.ai"）
    start_time_str = start_dt_local.strftime('%Y%m%dT%H%M%S')
    random_str = generate_random_string(6)
    uid = f"{start_time_str}-{random_str}@interview.ai"
    
    # 格式化时间
    # DTSTART/DTEND: 本地时间，不带Z，格式：YYYYMMDDTHHMMSS
    dtstart_str = start_dt_local.strftime('%Y%m%dT%H%M%S')
    dtend_str = end_dt_local.strftime('%Y%m%dT%H%M%S')
    
    # DTSTAMP: UTC时间，必须以Z结尾，格式：YYYYMMDDTHHMMSSZ
    dtstamp_str = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    
    # 转义特殊字符
    summary_escaped = escape_ics_text(title)
    location_escaped = escape_ics_text(location) if location else ""
    description_escaped = escape_ics_text(description) if description else "自动生成的面试邀约"
    
    # 生成 ICS 内容（严格按照 RFC 5545 标准）
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp_str}",
        f"SUMMARY:{summary_escaped}",
        f"DTSTART:{dtstart_str}",
        f"DTEND:{dtend_str}",
    ]
    
    # 添加地点（如果有）
    if location_escaped:
        ics_lines.append(f"LOCATION:{location_escaped}")
    
    # 添加描述（如果有）
    if description_escaped:
        ics_lines.append(f"DESCRIPTION:{description_escaped}")
    
    # 结束标记
    ics_lines.extend([
        "END:VEVENT",
        "END:VCALENDAR"
    ])
    
    # 组合成完整的ICS内容
    ics_content = "\n".join(ics_lines)
    
    # 确保输出目录存在
    out_dir = Path("reports/invites")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存文件（UTF-8编码）
    ics_path = out_dir / f"invite_{uid.replace('@', '_at_').replace(':', '_')}.ics"
    ics_path.write_text(ics_content, encoding="utf-8")
    
    return str(ics_path)
