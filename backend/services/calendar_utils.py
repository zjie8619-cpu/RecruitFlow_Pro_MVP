# backend/services/calendar_utils.py
"""
日历工具:生成 ICS 日历文件 (符合 RFC 5545 标准，兼容 iPhone、Android、QQ 邮箱)
"""
from pathlib import Path
from datetime import datetime, timedelta
import random
import string


def escape_ics_text(text: str) -> str:
    """
    转义 ICS 文本中的特殊字符（RFC 5545）
    注意：DESCRIPTION 中的换行必须使用 \\n，而不是实际换行
    """
    if not text:
        return ""
    # 先替换英文逗号为中文逗号（符合用户要求：DESCRIPTION中不得包含英文逗号）
    text = text.replace(',', '，')
    # 转义特殊字符（RFC 5545要求）
    text = text.replace('\\', '\\\\')  # 必须先转义反斜杠
    text = text.replace(';', '\\;')
    # 将实际换行转换为 \n（DESCRIPTION 中必须使用 \n 而不是实际换行）
    text = text.replace('\r\n', '\\n')
    text = text.replace('\r', '\\n')
    text = text.replace('\n', '\\n')
    return text


def generate_random_string(length: int = 6) -> str:
    """生成随机字符串（用于UID）"""
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
    # DTSTART/DTEND: 使用TZID指定时区，格式：YYYYMMDDTHHMMSS（不带Z）
    dtstart_str = start_dt_local.strftime('%Y%m%dT%H%M%S')
    dtend_str = end_dt_local.strftime('%Y%m%dT%H%M%S')
    
    # DTSTAMP: UTC时间，必须以Z结尾，格式：YYYYMMDDTHHMMSSZ
    dtstamp_str = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    
    # 时区处理：确保使用Asia/Shanghai（QQ邮箱、iOS、Android都需要TZID才能显示"加入日历"按钮）
    timezone_map = {
        "Asia/Shanghai": "Asia/Shanghai",
        "Asia/Beijing": "Asia/Shanghai",  # 北京和上海使用同一时区
    }
    tzid = timezone_map.get(timezone_str, "Asia/Shanghai")  # 默认使用Asia/Shanghai
    
    # 转义特殊字符（所有字段都必须存在，不能为空）
    summary_escaped = escape_ics_text(title) if title else "面试邀请"
    location_escaped = escape_ics_text(location) if location else "待确认"
    description_escaped = escape_ics_text(description) if description else "请准时参加面试。"
    
    # 生成 ICS 内容（严格按照 RFC 5545 标准，兼容 iPhone、Android、QQ 邮箱）
    # 注意：所有字段都必须存在，任何缺失都会导致 iOS 无法导入
    # 注意：使用 LF 换行符（\n），不使用 CRLF（\r\n）
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//InterviewAI//Schedule System//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp_str}",
        f"SUMMARY:{summary_escaped}",
        f"DTSTART;TZID={tzid}:{dtstart_str}",
        f"DTEND;TZID={tzid}:{dtend_str}",
        f"LOCATION:{location_escaped}",
        f"DESCRIPTION:{description_escaped}",
        "END:VEVENT",
        "END:VCALENDAR"
    ]
    
    # 组合成完整的ICS内容（使用 LF 换行符，确保 iOS 兼容）
    ics_content = "\n".join(ics_lines)
    
    # 确保输出目录存在
    out_dir = Path("reports/invites")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存文件（UTF-8编码，使用 LF 换行符）
    ics_path = out_dir / f"invite_{uid.replace('@', '_at_').replace(':', '_')}.ics"
    # 使用 newline='' 确保写入时使用 LF，而不是系统的默认换行符
    with open(ics_path, 'w', encoding='utf-8', newline='') as f:
        f.write(ics_content)
    
    return str(ics_path)
