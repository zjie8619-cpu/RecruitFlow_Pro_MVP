# backend/services/wechat_integration.py
"""
# 企业微信集成:生成邀约链接和发送消息
"""
from typing import Dict, Any, Optional
from urllib.parse import quote
import os
def generate_wechat_invite_link(
candidate_name: str,
candidate_email: str,
position: str,
interview_time: str,
highlights: str = "",
organizer_name: str = "HR",
organizer_wechat: str = ""
) -> str:
"""
#     生成企业微信邀约链接
Args:
#         candidate_name: 候选人姓名
#         candidate_email: 候选人邮箱
#         position: 岗位名称
#         interview_time: 面试时间(格式:2025-11-15 14:00)
#         highlights: 候选人亮点(可选)
#         organizer_name: 组织者姓名
#         organizer_wechat: 组织者企业微信ID(可选)
Returns:
#         企业微信邀约链接(字符串)
"""
# 构建邀约消息内容
#     message = f"""您好 {candidate_name},
# 关于「{position}」岗位,我们想与您安排一次面试.
# 面试时间:{interview_time}
# 面试方式:企业微信/Zoom视频会议
"""
if highlights:
#         message += f"初步评估亮点:{highlights}\n\n"
#     message += f"联系人:{organizer_name}"
if organizer_wechat:
#         message += f"(企业微信:{organizer_wechat})"
#     message += "\n\n期待与您交流!"
# 企业微信链接格式(需要企业微信应用配置)
# 方式1:通过企业微信应用发送(需要corpid和agentid)
# 方式2:生成企业微信外部联系人添加链接
# 方式3:生成企业微信会议链接
# 这里提供多种链接生成方式
wechat_link = ""
# 方式1:企业微信会议链接(推荐)
# 格式:https://meeting.tencent.com/dm/xxx
# 注意:需要先创建会议,这里提供模板
# 方式2:企业微信外部联系人添加链接
# 格式:weixin://dl/business/?t=xxx
# 注意:需要企业微信管理员配置
# 方式3:生成企业微信消息模板(供手动发送)
# 返回格式化的消息内容,HR可以复制到企业微信发送
return message
def generate_wechat_meeting_link(meeting_id: str = "") -> str:
"""
#     生成企业微信会议链接
Args:
#         meeting_id: 会议ID(如果已创建)
Returns:
#         企业微信会议链接
"""
if meeting_id:
return f"https://meeting.tencent.com/dm/{meeting_id}"
else:
# 返回创建会议的提示
#         return "https://meeting.tencent.com/(请先创建会议)"
def format_wechat_message(
candidate_name: str,
position: str,
interview_time: str,
highlights: str = "",
meeting_link: str = "",
organizer_name: str = "HR"
) -> str:
"""
#     格式化企业微信消息(供手动发送)
Args:
#         candidate_name: 候选人姓名
#         position: 岗位名称
#         interview_time: 面试时间
#         highlights: 候选人亮点
#         meeting_link: 会议链接
#         organizer_name: 组织者姓名
Returns:
#         格式化的企业微信消息文本
"""
#     message = f"""您好 {candidate_name},
# 关于「{position}」岗位,我们想与您安排一次面试.
# 📅 面试时间:{interview_time}
# 💻 面试方式:企业微信/Zoom视频会议
"""
if meeting_link:
#         message += f"🔗 会议链接:{meeting_link}\n"
if highlights:
#         message += f"\n✨ 初步评估亮点:{highlights}\n"
#     message += f"\n👤 联系人:{organizer_name}\n\n期待与您交流!"
return message
def create_wechat_invite_template(
invite_data: Dict[str, Any]
) -> Dict[str, Any]:
"""
#     创建企业微信邀约模板数据
Args:
#         invite_data: 邀约数据字典,包含:
#             - name: 候选人姓名
#             - email: 候选人邮箱
#             - position: 岗位名称
#             - interview_time: 面试时间
#             - highlights: 候选人亮点
#             - meeting_link: 会议链接(可选)
#             - organizer_name: 组织者姓名
#             - organizer_wechat: 组织者企业微信ID(可选)
Returns:
#         包含企业微信消息和链接的字典
"""
name = invite_data.get("name", "")
email = invite_data.get("email", "")
position = invite_data.get("position", "")
interview_time = invite_data.get("interview_time", "")
highlights = invite_data.get("highlights", "")
meeting_link = invite_data.get("meeting_link", "")
organizer_name = invite_data.get("organizer_name", "HR")
organizer_wechat = invite_data.get("organizer_wechat", "")
# 生成企业微信消息
wechat_message = format_wechat_message(
candidate_name=name,
position=position,
interview_time=interview_time,
highlights=highlights,
meeting_link=meeting_link,
organizer_name=organizer_name
)
# 生成企业微信链接(如果有配置)
wechat_link = ""
if organizer_wechat:
# 可以生成添加企业微信的链接
#         wechat_link = f"企业微信ID:{organizer_wechat}"
return {
"wechat_message": wechat_message,
"wechat_link": wechat_link,
"meeting_link": meeting_link or generate_wechat_meeting_link(),
#         "copy_ready": True  # 标记为可直接复制发送
}
"""
# 企业微信集成:生成邀约链接和发送消息
"""
from typing import Dict, Any, Optional
from urllib.parse import quote
import os
def generate_wechat_invite_link(
candidate_name: str,
candidate_email: str,
position: str,
interview_time: str,
highlights: str = "",
organizer_name: str = "HR",
organizer_wechat: str = ""
) -> str:
"""
#     生成企业微信邀约链接
Args:
#         candidate_name: 候选人姓名
#         candidate_email: 候选人邮箱
#         position: 岗位名称
#         interview_time: 面试时间(格式:2025-11-15 14:00)
#         highlights: 候选人亮点(可选)
#         organizer_name: 组织者姓名
#         organizer_wechat: 组织者企业微信ID(可选)
Returns:
#         企业微信邀约链接(字符串)
"""
# 构建邀约消息内容
#     message = f"""您好 {candidate_name},
# 关于「{position}」岗位,我们想与您安排一次面试.
# 面试时间:{interview_time}
# 面试方式:企业微信/Zoom视频会议
"""
if highlights:
#         message += f"初步评估亮点:{highlights}\n\n"
#     message += f"联系人:{organizer_name}"
if organizer_wechat:
#         message += f"(企业微信:{organizer_wechat})"
#     message += "\n\n期待与您交流!"
# 企业微信链接格式(需要企业微信应用配置)
# 方式1:通过企业微信应用发送(需要corpid和agentid)
# 方式2:生成企业微信外部联系人添加链接
# 方式3:生成企业微信会议链接
# 这里提供多种链接生成方式
wechat_link = ""
# 方式1:企业微信会议链接(推荐)
# 格式:https://meeting.tencent.com/dm/xxx
# 注意:需要先创建会议,这里提供模板
# 方式2:企业微信外部联系人添加链接
# 格式:weixin://dl/business/?t=xxx
# 注意:需要企业微信管理员配置
# 方式3:生成企业微信消息模板(供手动发送)
# 返回格式化的消息内容,HR可以复制到企业微信发送
return message
def generate_wechat_meeting_link(meeting_id: str = "") -> str:
"""
#     生成企业微信会议链接
Args:
#         meeting_id: 会议ID(如果已创建)
Returns:
#         企业微信会议链接
"""
if meeting_id:
return f"https://meeting.tencent.com/dm/{meeting_id}"
else:
# 返回创建会议的提示
#         return "https://meeting.tencent.com/(请先创建会议)"
def format_wechat_message(
candidate_name: str,
position: str,
interview_time: str,
highlights: str = "",
meeting_link: str = "",
organizer_name: str = "HR"
) -> str:
"""
#     格式化企业微信消息(供手动发送)
Args:
#         candidate_name: 候选人姓名
#         position: 岗位名称
#         interview_time: 面试时间
#         highlights: 候选人亮点
#         meeting_link: 会议链接
#         organizer_name: 组织者姓名
Returns:
#         格式化的企业微信消息文本
"""
#     message = f"""您好 {candidate_name},
# 关于「{position}」岗位,我们想与您安排一次面试.
# 📅 面试时间:{interview_time}
# 💻 面试方式:企业微信/Zoom视频会议
"""
if meeting_link:
#         message += f"🔗 会议链接:{meeting_link}\n"
if highlights:
#         message += f"\n✨ 初步评估亮点:{highlights}\n"
#     message += f"\n👤 联系人:{organizer_name}\n\n期待与您交流!"
return message
def create_wechat_invite_template(
invite_data: Dict[str, Any]
) -> Dict[str, Any]:
"""
#     创建企业微信邀约模板数据
Args:
#         invite_data: 邀约数据字典,包含:
#             - name: 候选人姓名
#             - email: 候选人邮箱
#             - position: 岗位名称
#             - interview_time: 面试时间
#             - highlights: 候选人亮点
#             - meeting_link: 会议链接(可选)
#             - organizer_name: 组织者姓名
#             - organizer_wechat: 组织者企业微信ID(可选)
Returns:
#         包含企业微信消息和链接的字典
"""
name = invite_data.get("name", "")
email = invite_data.get("email", "")
position = invite_data.get("position", "")
interview_time = invite_data.get("interview_time", "")
highlights = invite_data.get("highlights", "")
meeting_link = invite_data.get("meeting_link", "")
organizer_name = invite_data.get("organizer_name", "HR")
organizer_wechat = invite_data.get("organizer_wechat", "")
# 生成企业微信消息
wechat_message = format_wechat_message(
candidate_name=name,
position=position,
interview_time=interview_time,
highlights=highlights,
meeting_link=meeting_link,
organizer_name=organizer_name
)
# 生成企业微信链接(如果有配置)
wechat_link = ""
if organizer_wechat:
# 可以生成添加企业微信的链接
#         wechat_link = f"企业微信ID:{organizer_wechat}"
return {
"wechat_message": wechat_message,
"wechat_link": wechat_link,
"meeting_link": meeting_link or generate_wechat_meeting_link(),
#         "copy_ready": True  # 标记为可直接复制发送
}
