"""
资料管理服务
处理资料上传、查询、删除等业务逻辑
"""
from typing import List, Dict, Any, Optional, BinaryIO
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime
from database.models import Material, MaterialQuestion, Subject, Question, MaterialType, MaterialStatus, User
from utils.minio_client import minio_client
from services.text_extractor_service import TextExtractorService
import os
import uuid
import logging

logger = logging.getLogger(__name__)


class MaterialService:
    """资料服务类"""
    
    # 支持的文件类型
    ALLOWED_EXTENSIONS = {
        'pdf': 'application/pdf',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'txt': 'text/plain',
        'md': 'text/markdown',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png'
    }
    
    # 文件大小限制（50MB）
    MAX_FILE_SIZE = 50 * 1024 * 1024
    
    @staticmethod
    def validate_file(filename: str, file_size: int) -> tuple[bool, str]:
        """
        验证文件
        :param filename: 文件名
        :param file_size: 文件大小
        :return: (是否有效, 错误信息)
        """
        # 检查文件扩展名
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in MaterialService.ALLOWED_EXTENSIONS:
            return False, f"不支持的文件类型: {ext}"
        
        # 检查文件大小
        if file_size > MaterialService.MAX_FILE_SIZE:
            return False, f"文件大小超过限制（最大50MB）"
        
        return True, ""
    
    @staticmethod
    def generate_object_name(user_id: int, subject_id: int, filename: str) -> str:
        """
        生成MinIO对象名称
        :param user_id: 用户ID
        :param subject_id: 科目ID
        :param filename: 原始文件名
        :return: 对象名称
        """
        # 生成唯一ID
        unique_id = uuid.uuid4().hex[:8]
        
        # 获取文件扩展名
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        
        # 构建路径: materials/{user_id}/{subject_id}/{unique_id}_{filename}
        object_name = f"materials/{user_id}/{subject_id}/{unique_id}_{filename}"
        
        return object_name
    
    @staticmethod
    def upload_material(
        db: Session,
        user_id: int,
        subject_id: int,
        file_data: BinaryIO,
        filename: str,
        file_size: int,
        name: str,
        material_type: str = 'other',
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        上传资料
        :param db: 数据库会话
        :param user_id: 用户ID
        :param subject_id: 科目ID
        :param file_data: 文件数据流
        :param filename: 文件名
        :param file_size: 文件大小
        :param name: 资料名称
        :param material_type: 资料类型
        :param tags: 标签列表
        :return: 资料信息
        """
        # 1. 验证文件
        is_valid, error_msg = MaterialService.validate_file(filename, file_size)
        if not is_valid:
            raise ValueError(error_msg)
        
        # 2. 验证科目是否存在
        subject = db.query(Subject).filter(
            Subject.id == subject_id,
            Subject.user_id == user_id
        ).first()
        if not subject:
            raise ValueError("科目不存在或无权访问")
        
        # 3. 生成对象名称
        object_name = MaterialService.generate_object_name(user_id, subject_id, filename)
        
        # 4. 获取文件类型
        file_ext = filename.rsplit('.', 1)[-1].lower()
        content_type = MaterialService.ALLOWED_EXTENSIONS.get(file_ext, 'application/octet-stream')
        
        try:
            # 5. 上传到MinIO (不传递包含中文的metadata)
            minio_client.upload_file(
                file_data=file_data,
                object_name=object_name,
                content_type=content_type,
                metadata={
                    'user_id': str(user_id),
                    'subject_id': str(subject_id)
                    # 移除 original_filename，因为可能包含非ASCII字符
                }
            )
            
            # 6. 创建数据库记录
            material = Material(
                user_id=user_id,
                subject_id=subject_id,
                name=name,
                file_path=object_name,
                file_type=file_ext,
                file_size=file_size,
                material_type=MaterialType[material_type] if material_type in MaterialType.__members__ else MaterialType.other,
                tags=tags or [],
                status=MaterialStatus.processing  # 设置为处理中
            )
            
            db.add(material)
            db.commit()
            db.refresh(material)
            
            # 7. 异步提取文本（在后台线程中执行）
            try:
                # 重新读取文件数据用于文本提取
                file_data.seek(0)
                file_bytes = file_data.read()
                
                # 提取文本
                extracted_text = TextExtractorService.extract_text(
                    file_data=file_bytes,
                    file_type=file_ext,
                    use_ai_ocr=False  # 暂不使用AI OCR
                )
                
                # 更新资料状态和文本内容
                material.content_text = extracted_text
                material.status = MaterialStatus.ready
                db.commit()
                
                logger.info(f"资料 {material.id} 文本提取成功，长度: {len(extracted_text)}")
                
            except Exception as extract_error:
                # 文本提取失败，但文件已上传
                logger.error(f"文本提取失败: {str(extract_error)}")
                material.status = MaterialStatus.error
                material.error_message = f"文本提取失败: {str(extract_error)}"
                db.commit()
            
            return {
                "id": material.id,
                "name": material.name,
                "file_type": material.file_type,
                "file_size": material.file_size,
                "material_type": material.material_type.value,
                "status": material.status.value,
                "created_at": material.created_at.isoformat()
            }
            
        except Exception as e:
            # 上传失败，清理MinIO文件
            try:
                minio_client.delete_file(object_name)
            except:
                pass
            raise ValueError(f"上传失败: {str(e)}")
    
    @staticmethod
    def get_materials(
        db: Session,
        user_id: int,
        subject_id: Optional[int] = None,
        material_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取资料列表
        :param db: 数据库会话
        :param user_id: 用户ID
        :param subject_id: 科目ID（可选）
        :param material_type: 资料类型（可选）
        :param status: 状态（可选）
        :param search: 搜索关键词（可选）
        :return: 资料列表
        """
        # 计算用户可访问的科目集合（自己的 + 共享/公共科目），
        # 使共享科目下的资料对被共享用户可见
        from services.share_service import ShareService
        accessible_ids = ShareService.get_accessible_subject_ids(user_id, db)

        if subject_id is not None:
            # 指定科目：无访问权限直接返回空
            if subject_id not in accessible_ids:
                return []
            query = db.query(Material).filter(Material.subject_id == subject_id)
        else:
            if not accessible_ids:
                return []
            query = db.query(Material).filter(Material.subject_id.in_(accessible_ids))
        
        if material_type and material_type in MaterialType.__members__:
            query = query.filter(Material.material_type == MaterialType[material_type])
        
        if status and status in MaterialStatus.__members__:
            query = query.filter(Material.status == MaterialStatus[status])
        
        if search:
            query = query.filter(Material.name.like(f"%{search}%"))
        
        materials = query.order_by(Material.created_at.desc()).all()
        
        result = []
        for material in materials:
            # 获取科目名称
            subject = db.query(Subject).filter(Subject.id == material.subject_id).first()
            # 是否为本人上传（决定能否编辑/删除/生成题目）
            is_owner = material.user_id == user_id
            owner = None if is_owner else db.query(User).filter(User.id == material.user_id).first()
            
            result.append({
                "id": material.id,
                "name": material.name,
                "subject_id": material.subject_id,
                "subject_name": subject.name if subject else "未知科目",
                "file_type": material.file_type,
                "file_size": material.file_size,
                "material_type": material.material_type.value,
                "tags": material.tags or [],
                "question_count": material.question_count,
                "status": material.status.value,
                "is_owner": is_owner,
                "owner_username": owner.username if owner else None,
                "created_at": material.created_at.isoformat(),
                "updated_at": material.updated_at.isoformat()
            })
        
        return result
    
    @staticmethod
    def get_material_file(
        db: Session,
        material_id: int,
        user_id: int
    ):
        """
        获取资料文件流（用于后端中转下载/预览）
        权限：本人，或对该资料所属科目有访问权（共享/公共）
        :return: (stream_response, filename, content_type)
                 stream_response 为 urllib3 HTTPResponse，调用方负责 close/release_conn
        """
        material = db.query(Material).filter(Material.id == material_id).first()
        if not material:
            raise ValueError("资料不存在或无权访问")

        from services.share_service import ShareService
        if material.user_id != user_id and not ShareService.can_access_subject(user_id, material.subject_id, db):
            raise ValueError("资料不存在或无权访问")

        content_type = MaterialService.ALLOWED_EXTENSIONS.get(
            material.file_type, 'application/octet-stream'
        )

        # 构造下载文件名：资料名（缺扩展名时补上）
        base_name = material.name or f"material_{material.id}"
        if material.file_type and not base_name.lower().endswith('.' + material.file_type.lower()):
            filename = f"{base_name}.{material.file_type}"
        else:
            filename = base_name

        stream = minio_client.get_object_stream(material.file_path)
        return stream, filename, content_type

    @staticmethod
    def get_material_detail(
        db: Session,
        material_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        获取资料详情
        :param db: 数据库会话
        :param material_id: 资料ID
        :param user_id: 用户ID
        :return: 资料详情
        """
        # 验证权限：本人，或对该资料所属科目有访问权（共享/公共）
        material = db.query(Material).filter(Material.id == material_id).first()
        
        if not material:
            raise ValueError("资料不存在或无权访问")
        
        from services.share_service import ShareService
        is_owner = material.user_id == user_id
        if not is_owner and not ShareService.can_access_subject(user_id, material.subject_id, db):
            raise ValueError("资料不存在或无权访问")
        
        # 获取科目信息
        subject = db.query(Subject).filter(Subject.id == material.subject_id).first()
        # 资料上传者信息（共享场景展示来源）
        owner = None if is_owner else db.query(User).filter(User.id == material.user_id).first()
        
        # 获取关联的题目
        question_links = db.query(MaterialQuestion).filter(
            MaterialQuestion.material_id == material_id
        ).all()
        
        questions = []
        for link in question_links:
            question = db.query(Question).filter(Question.id == link.question_id).first()
            if question:
                questions.append({
                    "id": question.id,
                    "question": question.question[:100] + "..." if len(question.question) > 100 else question.question,
                    "type": question.type.value,
                    "confidence_score": float(link.confidence_score) if link.confidence_score else 0.8,
                    "generated_at": link.generated_at.isoformat()
                })
        
        # 文件通过后端中转下载（MinIO 端口不对外开放，不能用预签名直链）
        file_url = f"/api/materials/{material.id}/download?user_id={user_id}"
        
        return {
            "material": {
                "id": material.id,
                "name": material.name,
                "subject_id": material.subject_id,
                "subject_name": subject.name if subject else "未知科目",
                "file_type": material.file_type,
                "file_size": material.file_size,
                "file_url": file_url,
                "material_type": material.material_type.value,
                "tags": material.tags or [],
                "question_count": material.question_count,
                "status": material.status.value,
                "error_message": material.error_message,
                "content_text": material.content_text,  # 添加文本内容
                "is_owner": is_owner,
                "owner_username": owner.username if owner else None,
                "created_at": material.created_at.isoformat(),
                "updated_at": material.updated_at.isoformat()
            },
            "questions": questions
        }
    
    @staticmethod
    def update_material(
        db: Session,
        material_id: int,
        user_id: int,
        name: Optional[str] = None,
        material_type: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        更新资料信息
        :param db: 数据库会话
        :param material_id: 资料ID
        :param user_id: 用户ID
        :param name: 新名称
        :param material_type: 新类型
        :param tags: 新标签
        :return: 更新后的资料信息
        """
        # 验证权限
        material = db.query(Material).filter(
            Material.id == material_id,
            Material.user_id == user_id
        ).first()
        
        if not material:
            raise ValueError("资料不存在或无权访问")
        
        # 更新字段
        if name:
            material.name = name
        
        if material_type and material_type in MaterialType.__members__:
            material.material_type = MaterialType[material_type]
        
        if tags is not None:
            material.tags = tags
        
        db.commit()
        db.refresh(material)
        
        return {
            "id": material.id,
            "name": material.name,
            "material_type": material.material_type.value,
            "tags": material.tags or []
        }
    
    @staticmethod
    def delete_material(
        db: Session,
        material_id: int,
        user_id: int
    ) -> bool:
        """
        删除资料
        :param db: 数据库会话
        :param material_id: 资料ID
        :param user_id: 用户ID
        :return: 是否成功
        """
        # 验证权限
        material = db.query(Material).filter(
            Material.id == material_id,
            Material.user_id == user_id
        ).first()
        
        if not material:
            raise ValueError("资料不存在或无权访问")
        
        try:
            # 1. 删除MinIO文件
            minio_client.delete_file(material.file_path)
            
            # 2. 删除数据库记录（级联删除关联的题目关系）
            db.delete(material)
            db.commit()
            
            return True
        except Exception as e:
            db.rollback()
            raise ValueError(f"删除失败: {str(e)}")
    
    @staticmethod
    def extract_text_from_material(
        db: Session,
        material_id: int,
        user_id: int,
        use_ai_ocr: bool = False
    ) -> Dict[str, Any]:
        """
        手动触发文本提取
        :param db: 数据库会话
        :param material_id: 资料ID
        :param user_id: 用户ID
        :param use_ai_ocr: 是否使用AI OCR
        :return: 提取结果
        """
        # 验证权限
        material = db.query(Material).filter(
            Material.id == material_id,
            Material.user_id == user_id
        ).first()
        
        if not material:
            raise ValueError("资料不存在或无权访问")
        
        try:
            # 1. 从MinIO下载文件
            file_data = minio_client.download_file(material.file_path)
            
            # 2. 更新状态为处理中
            material.status = MaterialStatus.processing
            material.error_message = None
            db.commit()
            
            # 3. 提取文本
            extracted_text = TextExtractorService.extract_text(
                file_data=file_data,
                file_type=material.file_type,
                use_ai_ocr=use_ai_ocr
            )
            
            # 4. 保存提取的文本
            material.content_text = extracted_text
            material.status = MaterialStatus.ready
            db.commit()
            
            logger.info(f"资料 {material_id} 文本提取成功，长度: {len(extracted_text)}")
            
            return {
                "material_id": material_id,
                "status": "success",
                "text_length": len(extracted_text),
                "preview": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
            }
            
        except Exception as e:
            logger.error(f"文本提取失败: {str(e)}")
            material.status = MaterialStatus.error
            material.error_message = f"文本提取失败: {str(e)}"
            db.commit()
            raise ValueError(f"文本提取失败: {str(e)}")
