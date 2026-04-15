"""
AI题目生成服务
使用AI从文本内容生成练习题目
"""
import json
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from database.models import Material, Question, MaterialQuestion, Subject, QuestionType, MaterialStatus
from utils.ai_client import get_ai_client
from utils.Prompt import (
    GENERATE_SINGLE_CHOICE_FROM_MATERIAL,
    GENERATE_MULTIPLE_CHOICE_FROM_MATERIAL,
    GENERATE_JUDGE_FROM_MATERIAL,
    GENERATE_FILL_FROM_MATERIAL,
    GENERATE_MAJOR_FROM_MATERIAL,
    SYSTEM_ROLE_GENERATE_FROM_MATERIAL
)
import re

logger = logging.getLogger(__name__)


class AIQuestionGenerator:
    """AI题目生成器"""
    
    # 题型映射
    QUESTION_TYPE_MAP = {
        'single': '单选题',
        'multiple': '多选题',
        'judge': '判断题',
        'fill': '填空题',
        'major': '大题'
    }
    
    @staticmethod
    def split_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> List[str]:
        """
        将长文本分段处理
        :param text: 原始文本
        :param chunk_size: 每段大小
        :param overlap: 重叠字符数
        :return: 文本段列表
        """
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # 如果不是最后一段，尝试在句号处断开
            if end < len(text):
                # 查找最近的句号
                last_period = text.rfind('。', start, end)
                if last_period > start + chunk_size // 2:
                    end = last_period + 1
            
            chunks.append(text[start:end])
            start = end - overlap if end < len(text) else end
        
        return chunks
    
    @staticmethod
    def build_prompt(text: str, question_type: str, count: int, subject_name: str) -> str:
        """
        构建AI生成题目的Prompt
        :param text: 文本内容
        :param question_type: 题目类型
        :param count: 生成数量
        :param subject_name: 科目名称
        :return: Prompt字符串
        """
        prompt_templates = {
            'single': GENERATE_SINGLE_CHOICE_FROM_MATERIAL,
            'multiple': GENERATE_MULTIPLE_CHOICE_FROM_MATERIAL,
            'judge': GENERATE_JUDGE_FROM_MATERIAL,
            'fill': GENERATE_FILL_FROM_MATERIAL,
            'major': GENERATE_MAJOR_FROM_MATERIAL
        }
        
        template = prompt_templates.get(question_type)
        if not template:
            raise ValueError(f"不支持的题目类型: {question_type}")
        
        return template.format(
            subject_name=subject_name,
            count=count,
            text=text
        )
    
    @staticmethod
    def parse_ai_response(response_text: str, question_type: str) -> List[Dict[str, Any]]:
        """
        解析AI返回的JSON响应
        :param response_text: AI返回的文本
        :param question_type: 题目类型
        :return: 题目列表
        """
        try:
            # 提取JSON部分（可能包含其他文本）
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if not json_match:
                raise ValueError("未找到有效的JSON数组")
            
            json_str = json_match.group(0)
            questions = json.loads(json_str)
            
            if not isinstance(questions, list):
                raise ValueError("返回的不是数组格式")
            
            # 验证每个题目的格式
            validated_questions = []
            for q in questions:
                if not isinstance(q, dict):
                    continue
                
                if 'question' not in q or 'answer' not in q:
                    continue
                
                # 根据题型验证必需字段
                if question_type in ['single', 'multiple']:
                    if 'options' not in q or not isinstance(q['options'], dict):
                        continue
                
                validated_questions.append(q)
            
            return validated_questions
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
            raise ValueError(f"AI返回的格式无效: {str(e)}")
        except Exception as e:
            logger.error(f"响应解析失败: {str(e)}")
            raise ValueError(f"响应解析失败: {str(e)}")
    
    @staticmethod
    def generate_questions_from_text(
        db: Session,
        material_id: int,
        user_id: int,
        question_types: List[str],
        question_counts: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        从资料文本生成题目
        :param db: 数据库会话
        :param material_id: 资料ID
        :param user_id: 用户ID
        :param question_types: 题目类型列表
        :param question_counts: 每种题型的数量
        :return: 生成结果
        """
        # 1. 获取资料
        material = db.query(Material).filter(
            Material.id == material_id,
            Material.user_id == user_id
        ).first()
        
        if not material:
            raise ValueError("资料不存在或无权访问")
        
        if not material.content_text:
            raise ValueError("资料尚未提取文本内容，请先提取文本")
        
        if material.status != MaterialStatus.ready:
            raise ValueError(f"资料状态异常: {material.status.value}")
        
        # 2. 获取科目信息
        subject = db.query(Subject).filter(Subject.id == material.subject_id).first()
        subject_name = subject.name if subject else "未知科目"
        
        # 3. 获取AI客户端
        ai_client = get_ai_client(user_id, db)
        
        # 4. 分段处理文本
        text_chunks = AIQuestionGenerator.split_text(material.content_text)
        logger.info(f"文本分为 {len(text_chunks)} 段")
        
        # 5. 生成题目
        all_generated_questions = []
        generation_stats = {
            'total_requested': sum(question_counts.values()),
            'total_generated': 0,
            'by_type': {}
        }
        
        for q_type in question_types:
            count = question_counts.get(q_type, 0)
            if count <= 0:
                continue
            
            type_questions = []
            
            # 对每个文本段生成题目
            questions_per_chunk = max(1, count // len(text_chunks))
            remaining = count
            
            for i, chunk in enumerate(text_chunks):
                if remaining <= 0:
                    break
                
                # 最后一段生成剩余的所有题目
                chunk_count = remaining if i == len(text_chunks) - 1 else min(questions_per_chunk, remaining)
                
                try:
                    # 构建Prompt
                    prompt = AIQuestionGenerator.build_prompt(
                        text=chunk,
                        question_type=q_type,
                        count=chunk_count,
                        subject_name=subject_name
                    )
                    
                    # 调用AI生成
                    logger.info(f"生成 {q_type} 题目 {chunk_count} 道（第{i+1}/{len(text_chunks)}段）")
                    response = ai_client.chat([{"role": "user", "content": prompt}])
                    
                    # 解析响应
                    questions = AIQuestionGenerator.parse_ai_response(response, q_type)
                    type_questions.extend(questions)
                    remaining -= len(questions)
                    
                    logger.info(f"成功生成 {len(questions)} 道题目")
                    
                except Exception as e:
                    logger.error(f"生成题目失败: {str(e)}")
                    continue
            
            # 6. 保存生成的题目到数据库
            saved_count = 0
            for q_data in type_questions[:count]:  # 只保存请求数量的题目
                try:
                    # 创建题目
                    question = Question(
                        user_id=user_id,
                        subject_id=material.subject_id,
                        type=QuestionType[q_type],
                        question=q_data['question'],
                        options_json=json.dumps(q_data.get('options', {}), ensure_ascii=False),
                        answer=q_data['answer'],
                        analysis=q_data.get('analysis', '')
                    )
                    db.add(question)
                    db.flush()
                    
                    # 创建关联
                    link = MaterialQuestion(
                        material_id=material_id,
                        question_id=question.id,
                        confidence_score=0.85  # 默认置信度
                    )
                    db.add(link)
                    
                    saved_count += 1
                    all_generated_questions.append({
                        'id': question.id,
                        'type': q_type,
                        'question': q_data['question']
                    })
                    
                except Exception as e:
                    logger.error(f"保存题目失败: {str(e)}")
                    continue
            
            generation_stats['by_type'][q_type] = saved_count
            generation_stats['total_generated'] += saved_count
        
        # 7. 更新资料的题目数
        material.question_count = db.query(MaterialQuestion).filter(
            MaterialQuestion.material_id == material_id
        ).count()
        db.commit()
        
        logger.info(f"题目生成完成: 请求{generation_stats['total_requested']}道，实际生成{generation_stats['total_generated']}道")
        
        return {
            'material_id': material_id,
            'statistics': generation_stats,
            'questions': all_generated_questions
        }
