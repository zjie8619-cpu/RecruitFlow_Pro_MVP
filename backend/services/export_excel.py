import os
from typing import Optional

import pandas as pd
from openpyxl import load_workbook

DEFAULT_TEMPLATE_PATH = r"C:\RecruitFlow_Pro_MVP\docs\课程顾问_能力维度评分表 (改).xlsx"

# 兼容旧版本:如果外部已有 TEMPLATE_PATH 定义，保持不冲突
TEMPLATE_PATH = globals().get("TEMPLATE_PATH", DEFAULT_TEMPLATE_PATH)


def export_competency_excel(data_df, output_path, template_path: Optional[str] = None):
    """
    强制使用《能力维度评分表(改)》模板格式进行导出
    """

    template_path = template_path or globals().get("TEMPLATE_PATH") or DEFAULT_TEMPLATE_PATH

    if not os.path.exists(template_path):
        raise FileNotFoundError(
            f"模板文件不存在: {template_path}. 请确认《能力维度评分表 (改).xlsx》已放在 docs 目录。"
        )

    # --- 读取模板 ---
    wb = load_workbook(template_path)
    ws = wb.active

    # 找到模板最后一行
    start_row = ws.max_row + 1

    # --- 写入数据 ---
    for _, row in data_df.iterrows():
        ws.append(row.tolist())

    # --- 保存 ---
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    wb.save(output_path)

    return output_path
