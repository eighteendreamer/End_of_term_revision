"""
题目导入路由（文件/图片导入 + AI 解析）
"""
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel
import os
import tempfile
from database.db import get_default_db
from database.models import LLMModel, Subject
from services.ai_parser import create_ai_parser
from services.question_service import QuestionService

router = APIRouter(prefix="/api/import", tags=["题目导入"])


class ImportResponse(BaseModel):
    """导入响应"""
    success: bool
    message: str
    count: int


class PreviewResponse(BaseModel):
    """预览响应"""
    success: bool
    message: str
    questions: List[Dict[str, Any]]


class TextImportRequest(BaseModel):
    """文本导入请求"""
    user_id: int
    subject_id: int
    text: str


class ConfirmImportRequest(BaseModel):
    """确认导入请求"""
    user_id: int
    subject_id: int
    questions: List[Dict[str, Any]]


# ==================== 新的两步导入流程 ====================

@router.post("/preview/file")
async def preview_from_file(
    user_id: int = Form(...),
    subject_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_default_db)
):
    """
    从文件预览题目（第一步：AI解析，不保存）
    """
    # 获取用户的 LLM 配置
    llm_config = db.query(LLMModel).filter(LLMModel.user_id == user_id).first()
    if not llm_config:
        raise HTTPException(status_code=400, detail="请先配置 AI 模型")
    
    # 获取科目信息（验证用户权限）
    subject = db.query(Subject).filter(
        Subject.id == subject_id,
        Subject.user_id == user_id
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在或无权访问")
    
    tmp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        parser = create_ai_parser(
            base_url=llm_config.base_url,
            api_key=llm_config.api_key,
            model_name=llm_config.model_name
        )
        
        parsed_data = parser.parse_file_to_questions(tmp_file_path, subject.name)
        
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        
        if not parsed_data.get("questions"):
            raise HTTPException(status_code=400, detail="AI未能从文件中解析出任何题目，请检查文件内容")
        
        return {
            "code": 200,
            "message": f"成功解析 {len(parsed_data['questions'])} 道题目",
            "data": {
                "questions": parsed_data["questions"]
            }
        }
    
    except HTTPException:
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.unlink(tmp_file_path)
            except:
                pass
        raise
    except Exception as e:
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.unlink(tmp_file_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.post("/preview/image")
async def preview_from_image(
    user_id: int = Form(...),
    subject_id: int = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_default_db)
):
    """
    从图片预览题目（第一步：AI解析，不保存）
    """
    import traceback
    
    # 获取用户的 LLM 配置
    llm_config = db.query(LLMModel).filter(LLMModel.user_id == user_id).first()
    if not llm_config:
        raise HTTPException(status_code=400, detail="请先在「AI 模型配置」页面添加模型配置")
    
    # 获取科目信息（验证用户权限）
    subject = db.query(Subject).filter(
        Subject.id == subject_id,
        Subject.user_id == user_id
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在或无权访问")
    
    tmp_file_path = None
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(image.filename)[1]) as tmp_file:
            content = await image.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        print(f"[预览图片] 用户ID: {user_id}, 科目: {subject.name}, 文件: {image.filename}")
        
        parser = create_ai_parser(
            base_url=llm_config.base_url,
            api_key=llm_config.api_key,
            model_name=llm_config.model_name
        )
        
        print(f"[AI解析] 开始OCR识别和AI解析...")
        
        parsed_data = parser.parse_image_to_questions(tmp_file_path, subject.name)
        
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        
        if not parsed_data.get("questions"):
            raise ValueError("AI未能从图片中识别出题目，请确保图片清晰且包含完整题目")
        
        print(f"[AI解析] 成功解析 {len(parsed_data['questions'])} 道题目")
        
        return {
            "code": 200,
            "message": f"成功解析 {len(parsed_data['questions'])} 道题目",
            "data": {
                "questions": parsed_data["questions"]
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        error_detail = str(e)
        error_traceback = traceback.format_exc()
        
        print(f"[解析错误] {error_detail}")
        print(error_traceback)
        
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.unlink(tmp_file_path)
            except:
                pass
        
        if "tesseract" in error_detail.lower():
            raise HTTPException(status_code=500, detail="OCR引擎未安装，请先安装 Tesseract OCR")
        elif "openai" in error_detail.lower() or "api" in error_detail.lower():
            raise HTTPException(status_code=500, detail=f"AI API调用失败: {error_detail}")
        else:
            raise HTTPException(status_code=500, detail=f"解析失败: {error_detail}")


@router.post("/preview/text")
def preview_from_text(
    request: TextImportRequest,
    db: Session = Depends(get_default_db)
):
    """
    从文本预览题目（第一步：AI解析，不保存）
    """
    # 获取用户的 LLM 配置
    llm_config = db.query(LLMModel).filter(LLMModel.user_id == request.user_id).first()
    if not llm_config:
        raise HTTPException(status_code=400, detail="请先配置 AI 模型")
    
    # 获取科目信息（验证用户权限）
    subject = db.query(Subject).filter(
        Subject.id == request.subject_id,
        Subject.user_id == request.user_id
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在或无权访问")
    
    try:
        parser = create_ai_parser(
            base_url=llm_config.base_url,
            api_key=llm_config.api_key,
            model_name=llm_config.model_name
        )
        
        parsed_data = parser.parse_text_to_questions(request.text, subject.name)
        
        if not parsed_data.get("questions"):
            raise HTTPException(status_code=400, detail="AI未能从文本中解析出任何题目")
        
        return {
            "code": 200,
            "message": f"成功解析 {len(parsed_data['questions'])} 道题目",
            "data": {
                "questions": parsed_data["questions"]
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.post("/confirm")
def confirm_import(
    request: ConfirmImportRequest,
    db: Session = Depends(get_default_db)
):
    """
    确认导入题目（第二步：保存到数据库）
    """
    # 验证科目权限
    subject = db.query(Subject).filter(
        Subject.id == request.subject_id,
        Subject.user_id == request.user_id
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在或无权访问")
    
    try:
        # 批量创建题目（含去重）
        result = QuestionService.batch_create_questions(
            db=db,
            user_id=request.user_id,
            subject_id=request.subject_id,
            questions_data=request.questions,
            skip_duplicates=True
        )
        
        message = f"成功导入 {result['created_count']} 道题目"
        if result['skipped_count'] > 0:
            message += f"（跳过 {result['skipped_count']} 道重复题目）"
        
        return {
            "code": 200,
            "message": message,
            "data": {
                "created_count": result['created_count'],
                "skipped_count": result['skipped_count']
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


# ==================== 旧的一步导入流程（保留兼容） ====================

async def import_from_file(
    user_id: int = Form(...),
    subject_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_default_db)
):
    """
    从文件导入题目（支持 PDF、Word、文本）
    """
    # 获取用户的 LLM 配置
    llm_config = db.query(LLMModel).filter(LLMModel.user_id == user_id).first()
    if not llm_config:
        raise HTTPException(status_code=400, detail="请先配置 AI 模型")
    
    # 获取科目信息（验证用户权限）
    subject = db.query(Subject).filter(
        Subject.id == subject_id,
        Subject.user_id == user_id
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在或无权访问")
    
    tmp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        parser = create_ai_parser(
            base_url=llm_config.base_url,
            api_key=llm_config.api_key,
            model_name=llm_config.model_name
        )
        
        parsed_data = parser.parse_file_to_questions(tmp_file_path, subject.name)
        
        if not parsed_data.get("questions"):
            raise HTTPException(status_code=400, detail="AI未能从文件中解析出任何题目，请检查文件内容是否为清晰的试题文本或适当拆分后重试")
        
        result = QuestionService.batch_create_questions(
            db=db,
            user_id=user_id,
            subject_id=subject_id,
            questions_data=parsed_data["questions"],
            skip_duplicates=True
        )
        
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        
        message = f"成功导入 {result['created_count']} 道题目"
        if result['skipped_count'] > 0:
            message += f"（跳过 {result['skipped_count']} 道重复题目）"
        
        return ImportResponse(
            success=True,
            message=message,
            count=result['created_count']
        )
    
    except HTTPException:
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.unlink(tmp_file_path)
            except:
                pass
        raise
    except Exception as e:
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.unlink(tmp_file_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.post("/image", response_model=ImportResponse)
async def import_from_image(
    user_id: int = Form(...),
    subject_id: int = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_default_db)
):
    """
    从图片导入题目（OCR + AI 解析）
    """
    import traceback
    
    # 获取用户的 LLM 配置
    llm_config = db.query(LLMModel).filter(LLMModel.user_id == user_id).first()
    if not llm_config:
        raise HTTPException(status_code=400, detail="请先在「AI 模型配置」页面添加模型配置")
    
    # 获取科目信息（验证用户权限）
    subject = db.query(Subject).filter(
        Subject.id == subject_id,
        Subject.user_id == user_id
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在或无权访问")
    
    tmp_file_path = None
    
    # 保存上传的图片到临时目录
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(image.filename)[1]) as tmp_file:
            content = await image.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        print(f"[导入图片] 用户ID: {user_id}, 科目: {subject.name}, 文件: {image.filename}")
        
        # 创建 AI 解析器
        parser = create_ai_parser(
            base_url=llm_config.base_url,
            api_key=llm_config.api_key,
            model_name=llm_config.model_name
        )
        
        print(f"[AI解析] 开始OCR识别和AI解析...")
        
        # 解析图片
        parsed_data = parser.parse_image_to_questions(tmp_file_path, subject.name)
        
        if not parsed_data.get("questions"):
            raise ValueError("AI未能从图片中识别出题目，请确保图片清晰且包含完整题目")
        
        print(f"[AI解析] 成功解析 {len(parsed_data['questions'])} 道题目")
        
        # 批量创建题目（含去重）
        result = QuestionService.batch_create_questions(
            db=db,
            user_id=user_id,
            subject_id=subject_id,
            questions_data=parsed_data["questions"],
            skip_duplicates=True
        )
        
        # 删除临时文件
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        
        message = f"成功导入 {result['created_count']} 道题目"
        if result['skipped_count'] > 0:
            message += f"（跳过 {result['skipped_count']} 道重复题目）"
        
        return ImportResponse(
            success=True,
            message=message,
            count=result['created_count']
        )
    
    except HTTPException:
        raise
    except Exception as e:
        error_detail = str(e)
        error_traceback = traceback.format_exc()
        
        print(f"[导入错误] {error_detail}")
        print(error_traceback)
        
        # 清理临时文件
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.unlink(tmp_file_path)
            except:
                pass
        
        # 提供更友好的错误信息
        if "tesseract" in error_detail.lower():
            raise HTTPException(status_code=500, detail="OCR引擎未安装，请先安装 Tesseract OCR")
        elif "openai" in error_detail.lower() or "api" in error_detail.lower():
            raise HTTPException(status_code=500, detail=f"AI API调用失败: {error_detail}")
        else:
            raise HTTPException(status_code=500, detail=f"导入失败: {error_detail}")


@router.post("/text", response_model=ImportResponse)
def import_from_text(
    request: TextImportRequest,
    db: Session = Depends(get_default_db)
):
    """
    从文本导入题目（直接解析文本）
    """
    # 获取用户的 LLM 配置
    llm_config = db.query(LLMModel).filter(LLMModel.user_id == request.user_id).first()
    if not llm_config:
        raise HTTPException(status_code=400, detail="请先配置 AI 模型")
    
    # 获取科目信息（验证用户权限）
    subject = db.query(Subject).filter(
        Subject.id == request.subject_id,
        Subject.user_id == request.user_id
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在或无权访问")
    
    try:
        parser = create_ai_parser(
            base_url=llm_config.base_url,
            api_key=llm_config.api_key,
            model_name=llm_config.model_name
        )
        
        parsed_data = parser.parse_text_to_questions(request.text, subject.name)
        if not parsed_data.get("questions"):
            raise HTTPException(status_code=400, detail="AI未能从文本中解析出任何题目，请确认文本包含清晰的题号、选项和答案信息")
        
        result = QuestionService.batch_create_questions(
            db=db,
            user_id=request.user_id,
            subject_id=request.subject_id,
            questions_data=parsed_data["questions"],
            skip_duplicates=True
        )
        
        message = f"成功导入 {result['created_count']} 道题目"
        if result['skipped_count'] > 0:
            message += f"（跳过 {result['skipped_count']} 道重复题目）"
        
        return ImportResponse(
            success=True,
            message=message,
            count=result['created_count']
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")
