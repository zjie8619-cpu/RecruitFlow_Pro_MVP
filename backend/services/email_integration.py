# backend/services/email_integration.py
"""
邮件集成:发送邮件到企业邮箱或生成导入文件
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, List, Optional
from pathlib import Path
import os
from datetime import datetime


def send_email_via_smtp(
    to_email: str,
    subject: str,
    body: str,
    ics_path: str = "",
    smtp_server: str = "",
    smtp_port: int = 587,
    smtp_user: str = "",
    smtp_password: str = "",
    from_email: str = ""
) -> Dict[str, Any]:
    """
    通过SMTP发送邮件到企业邮箱
    
    Args:
        to_email: 收件人邮箱
        subject: 邮件主题
        body: 邮件正文
        ics_path: ICS日历文件路径(可选)
        smtp_server: SMTP服务器地址(如:smtp.exmail.qq.com)
        smtp_port: SMTP端口(默认587)
        smtp_user: SMTP用户名(邮箱地址)
        smtp_password: SMTP密码或授权码
        from_email: 发件人邮箱
    
    Returns:
        发送结果字典,包含 success 和 message
    """
    if not smtp_server or not smtp_user or not smtp_password:
        return {
            "success": False,
            "message": "SMTP配置不完整,请检查 .env 文件中的邮件配置"
        }
    
    try:
        # 创建邮件对象
        msg = MIMEMultipart()
        msg['From'] = from_email or smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # 添加邮件正文
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # 添加ICS附件
        if ics_path and os.path.exists(ics_path):
            with open(ics_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {os.path.basename(ics_path)}'
                )
                msg.attach(part)
        
        # 连接SMTP服务器并发送
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # 启用TLS加密（QQ企业邮箱需要）
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        
        return {
            "success": True,
            "message": f"邮件已成功发送到 {to_email}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"邮件发送失败: {str(e)}"
        }


def generate_email_import_file(
    invite_results: List[Dict[str, Any]],
    output_dir: str = "reports/emails"
) -> str:
    """
    生成邮件导入文件(.eml格式),可用于导入企业邮箱
    
    Args:
        invite_results: 邀约结果列表
        output_dir: 输出目录
    
    Returns:
        生成的邮件文件路径
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    email_files = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for idx, invite in enumerate(invite_results):
        name = invite.get("name", f"候选人{idx+1}")
        email = invite.get("email", "")
        body = invite.get("body", "")
        ics_path = invite.get("ics", "")
        position = invite.get("position", "目标岗位")
        
        # 生成邮件主题
        subject = f"面试邀约 - {position} - {name}"
        
        # 创建EML文件内容
        eml_content = f"""From: HR Team <hr@company.com>
To: {email}
Subject: {subject}
Date: {datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0800')}
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: 8bit

{body}
"""
        
        # 如果有ICS附件,添加附件信息
        if ics_path and os.path.exists(ics_path):
            # 读取ICS文件内容并编码
            with open(ics_path, 'rb') as f:
                ics_content = f.read()
                import base64
                ics_base64 = base64.b64encode(ics_content).decode('utf-8')
                
                eml_content += f"""
--boundary
Content-Type: text/calendar; charset=utf-8; method=REQUEST
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename="{os.path.basename(ics_path)}"

{ics_base64}
--boundary--
"""
        
        # 保存EML文件
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        eml_path = os.path.join(output_dir, f"invite_{safe_name}_{timestamp}_{idx+1}.eml")
        with open(eml_path, 'w', encoding='utf-8') as f:
            f.write(eml_content)
        
        email_files.append(eml_path)
    
    # 返回第一个文件路径(或创建批量导入说明文件)
    if email_files:
        # 创建批量导入说明文件
        readme_path = os.path.join(output_dir, f"批量导入说明_{timestamp}.txt")
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(f"""邮件批量导入说明
生成时间:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
邮件数量:{len(email_files)}

导入方法:
1. Outlook:
   - 打开 Outlook
   - 文件 -> 打开 -> 其他文件
   - 选择 .eml 文件导入

2. 企业邮箱(网页版):
   - 登录企业邮箱
   - 设置 -> 导入邮件
   - 选择 .eml 文件导入

3. 企业邮箱(客户端):
   - 使用邮件客户端(如 Foxmail、Thunderbird)
   - 导入 .eml 文件

生成的文件列表:
""")
            for eml_file in email_files:
                f.write(f"- {os.path.basename(eml_file)}\n")
        
        return readme_path
    
    return ""


def generate_outlook_import_csv(
    invite_results: List[Dict[str, Any]],
    output_path: str = "reports/emails/outlook_import.csv"
) -> str:
    """
    生成Outlook导入CSV文件(用于批量导入联系人/邮件)
    
    Args:
        invite_results: 邀约结果列表
        output_path: 输出文件路径
    
    Returns:
        生成的CSV文件路径
    """
    import pandas as pd
    
    Path(os.path.dirname(output_path)).mkdir(parents=True, exist_ok=True)
    
    # 准备数据
    rows = []
    for invite in invite_results:
        rows.append({
            "姓名": invite.get("name", ""),
            "邮箱": invite.get("email", ""),
            "职位": invite.get("position", ""),
            "评分": invite.get("score", ""),
            "亮点": invite.get("highlights", ""),
            "邮件内容": invite.get("body", ""),
            "ICS文件": invite.get("ics", ""),
        })
    
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    
    return output_path
