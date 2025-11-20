"""
# 导出 API 路由
# 提供 Excel 导出功能�?HTTP API 接口
"""
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from typing import List, Dict, Any
from pydantic import BaseModel

from backend.services.export_excel import export_competency_excel
import pandas as pd

router = APIRouter(prefix="/api/export", tags=["export"])


class DimensionItem(BaseModel):
    """能力维度数据模型"""
    name: str
    description: str
    interview_question: str
    score20: str
    score60: str
    score100: str
    weight: float = 0.0
    score_points: str = ""


class ExportRequest(BaseModel):
    """导出请求模型"""
    job_title: str
    dimensions: List[DimensionItem]


@router.post("/ability-sheet")
async def export_ability_sheet_api(request: ExportRequest):
    """
#     导出能力维度评分�?Excel
    
    Args:
#         request: 导出请求,包含岗位名称和能力维度列表
    
    Returns:
#         Excel 文件二进制流
    """
    try:
        rows = []
        for dim in request.dimensions:
            rows.append({
                "能力维度": dim.name,
                "说明": dim.description,
                "面试题目": dim.interview_question,
                "评分要点": dim.score_points,
                "20分行为表现": dim.score20,
                "60分行为表现": dim.score60,
                "100分行为表现": dim.score100,
                "权重": dim.weight,
            })

        data_df = pd.DataFrame(rows)
        output_path = r"C:\RecruitFlow_Pro_MVP\docs\课程顾问_能力维度评分表(改)_输出.xlsx"

        excel_bytes, saved_path = export_competency_excel(
            data_df,
            output_path=output_path,
            job_title=request.job_title,
        )

        filename = f"{request.job_title}_能力维度评分表.xlsx"
        if saved_path and saved_path != output_path:
            filename = os.path.basename(saved_path)

        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"模板文件不存在: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")
