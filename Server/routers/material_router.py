"""
资料管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from urllib.parse import quote
from database.db import get_default_db
from services.material_service import MaterialService
import json

router = APIRouter(prefix="/api/materials", tags=["materials"])


# ============================================================
# 请求/响应模型
# ============================================================

class UpdateMaterialRequest(BaseModel):
    """更新资料请求"""
    user_id: int
    name: Optional[str] = None
    material_type: Optional[str] = None
    tags: Optional[List[str]] = None


# ============================================================
# API 路由
# ============================================================

@router.post("")
async def upload_material(
    file: UploadFile = File(...),
    user_id: int = Form(...),
    subject_id: int = Form(...),
    name: str = Form(...),
    material_type: str = Form("other"),
    tags: str = Form("[]"),
    db: Session = Depends(get_default_db)
):
    """
    上传资料
    """
    try:
        # 解析tags
        tags_list = json.loads(tags) if tags else []
        
        # 读取文件
        file_data = await file.read()
        file_size = len(file_data)
        
        # 创建文件流
        from io import BytesIO
        file_stream = BytesIO(file_data)
        
        # 上传资料
        result = MaterialService.upload_material(
            db=db,
            user_id=user_id,
            subject_id=subject_id,
            file_data=file_stream,
            filename=file.filename,
            file_size=file_size,
            name=name,
            material_type=material_type,
            tags=tags_list
        )
        
        return {"code": 200, "message": "上传成功", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("")
async def get_materials(
    user_id: int,
    subject_id: Optional[int] = None,
    material_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_default_db)
):
    """
    获取资料列表
    """
    try:
        materials = MaterialService.get_materials(
            db=db,
            user_id=user_id,
            subject_id=subject_id,
            material_type=material_type,
            status=status,
            search=search
        )
        return {"code": 200, "message": "获取成功", "data": {"materials": materials}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取资料列表失败: {str(e)}")


@router.get("/{material_id}/download")
async def download_material(
    material_id: int,
    user_id: int,
    db: Session = Depends(get_default_db)
):
    """
    下载/预览资料文件（经后端中转，从 MinIO 取流返回，前端不直接访问 MinIO）
    """
    try:
        stream, filename, content_type = MaterialService.get_material_file(
            db=db,
            material_id=material_id,
            user_id=user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")

    def iter_file():
        try:
            for chunk in stream.stream(32 * 1024):
                yield chunk
        finally:
            stream.close()
            stream.release_conn()

    # 文件名做 URL 编码以支持中文（RFC 5987）
    encoded_name = quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"
    }
    return StreamingResponse(iter_file(), media_type=content_type, headers=headers)


@router.get("/{material_id}")
async def get_material_detail(
    material_id: int,
    user_id: int,
    db: Session = Depends(get_default_db)
):
    """
    获取资料详情
    """
    try:
        detail = MaterialService.get_material_detail(
            db=db,
            material_id=material_id,
            user_id=user_id
        )
        return {"code": 200, "message": "获取成功", "data": detail}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取资料详情失败: {str(e)}")


@router.put("/{material_id}")
async def update_material(
    material_id: int,
    request: UpdateMaterialRequest,
    db: Session = Depends(get_default_db)
):
    """
    更新资料信息
    """
    try:
        result = MaterialService.update_material(
            db=db,
            material_id=material_id,
            user_id=request.user_id,
            name=request.name,
            material_type=request.material_type,
            tags=request.tags
        )
        return {"code": 200, "message": "更新成功", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.delete("/{material_id}")
async def delete_material(
    material_id: int,
    user_id: int,
    db: Session = Depends(get_default_db)
):
    """
    删除资料
    """
    try:
        MaterialService.delete_material(
            db=db,
            material_id=material_id,
            user_id=user_id
        )
        return {"code": 200, "message": "删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.post("/{material_id}/extract-text")
async def extract_text(
    material_id: int,
    user_id: int,
    use_ai_ocr: bool = False,
    db: Session = Depends(get_default_db)
):
    """
    手动触发文本提取
    """
    try:
        result = MaterialService.extract_text_from_material(
            db=db,
            material_id=material_id,
            user_id=user_id,
            use_ai_ocr=use_ai_ocr
        )
        return {"code": 200, "message": "文本提取成功", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文本提取失败: {str(e)}")


class GenerateQuestionsRequest(BaseModel):
    """生成题目请求"""
    user_id: int
    question_types: List[str]  # ['single', 'multiple', 'judge', 'fill', 'major']
    question_counts: dict  # {'single': 10, 'multiple': 5, ...}


@router.post("/{material_id}/generate-questions")
async def generate_questions(
    material_id: int,
    request: GenerateQuestionsRequest,
    db: Session = Depends(get_default_db)
):
    """
    从资料生成题目
    """
    try:
        from services.ai_question_generator import AIQuestionGenerator
        
        result = AIQuestionGenerator.generate_questions_from_text(
            db=db,
            material_id=material_id,
            user_id=request.user_id,
            question_types=request.question_types,
            question_counts=request.question_counts
        )
        return {"code": 200, "message": "题目生成成功", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"题目生成失败: {str(e)}")
