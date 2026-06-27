"""
SQLAlchemy ORM 模型定义
"""
from sqlalchemy import Column, BigInteger, String, Integer, Text, Enum, TIMESTAMP, ForeignKey, JSON
from sqlalchemy.sql import func
from database.db import Base
import enum


class QuestionType(enum.Enum):
    """题目类型枚举"""
    single = "single"      # 单选
    multiple = "multiple"  # 多选
    judge = "judge"        # 判断
    fill = "fill"          # 填空
    major = "major"        # 大型题


class ShareType(enum.Enum):
    """共享类型枚举"""
    USER = "USER"      # 指定用户共享
    PUBLIC = "PUBLIC"  # 公共共享


class GenderType(enum.Enum):
    """性别类型枚举"""
    male = "male"      # 男
    female = "female"  # 女
    hidden = "hidden"  # 隐藏



class GenderType(enum.Enum):
    """性别类型枚举"""
    male = "male"      # 男
    female = "female"  # 女
    hidden = "hidden"  # 隐藏


class VisibilityLevel(enum.Enum):
    """可见级别枚举"""
    private = "private"    # 私有
    major = "major"        # 专业级
    college = "college"    # 学院级
    school = "school"      # 校级
    public = "public"      # 公开


class PermissionLevel(enum.Enum):
    """权限级别枚举"""
    read = "read"      # 只读
    write = "write"    # 读写
    admin = "admin"    # 管理


class ResourceType(enum.Enum):
    """资源类型枚举"""
    subject = "subject"    # 科目
    question = "question"  # 题目


# ============================================================
# 组织架构表
# ============================================================

class School(Base):
    """学校表"""
    __tablename__ = "schools"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='学校ID')
    name = Column(String(255), nullable=False, unique=True, comment='学校名称')
    # code = Column(String(50), nullable=True, comment='学校代码')  # 数据库中没有此字段
    province = Column(String(50), nullable=True, comment='省份')
    city = Column(String(50), nullable=True, comment='城市')
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), comment='创建时间')
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), comment='更新时间')


class College(Base):
    """学院表（二级学院）"""
    __tablename__ = "colleges"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='学院ID')
    school_id = Column(BigInteger, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False, comment='所属学校ID')
    name = Column(String(255), nullable=False, comment='学院名称')
    # code = Column(String(50), nullable=True, comment='学院代码')  # 数据库中没有此字段
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), comment='创建时间')
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), comment='更新时间')


class Major(Base):
    """专业表"""
    __tablename__ = "majors"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='专业ID')
    college_id = Column(BigInteger, ForeignKey('colleges.id', ondelete='CASCADE'), nullable=False, comment='所属学院ID')
    school_id = Column(BigInteger, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False, comment='所属学校ID（冗余字段）')
    name = Column(String(255), nullable=False, comment='专业名称')
    # code = Column(String(50), nullable=True, comment='专业代码')  # 数据库中没有此字段
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), comment='创建时间')
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), comment='更新时间')


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='用户主键 ID')
    student_id = Column(String(50), unique=True, nullable=False, comment='学号（唯一，用于登录）')
    school_id = Column(BigInteger, ForeignKey('schools.id', ondelete='SET NULL'), nullable=True, comment='所属学校ID')
    college_id = Column(BigInteger, ForeignKey('colleges.id', ondelete='SET NULL'), nullable=True, comment='所属学院ID')
    major_id = Column(BigInteger, ForeignKey('majors.id', ondelete='SET NULL'), nullable=True, comment='所属专业ID')
    username = Column(String(255), nullable=False, comment='用户名')
    password_hash = Column(String(255), nullable=False, comment='密码哈希值（加密存储）')
    class_name = Column(String(100), nullable=True, comment='班级')
    gender = Column(Enum(GenderType), nullable=True, comment='性别：male=男，female=女，hidden=隐藏')
    profile_completed = Column(Integer, default=0, comment='账号信息是否完善：0=未完善，1=已完善')
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), comment='创建时间')
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), comment='更新时间')


class DBConfig(Base):
    """用户自定义数据库配置表"""
    __tablename__ = "db_configs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='数据库配置 ID')
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='所属用户 ID')
    db_host = Column(String(255), nullable=False, comment='数据库主机地址')
    db_port = Column(Integer, nullable=False, comment='数据库端口号')
    db_user = Column(String(255), nullable=False, comment='数据库用户名')
    db_password = Column(String(255), nullable=False, comment='数据库密码')
    db_name = Column(String(255), nullable=False, comment='数据库名')
    is_active = Column(Integer, default=0, comment='是否是当前使用的数据库配置')
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), comment='创建时间')


class LLMModel(Base):
    """用户自定义大模型配置表"""
    __tablename__ = "llm_models"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='模型配置 ID')
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='所属用户 ID')
    model_name = Column(String(255), nullable=False, comment='模型名称')
    base_url = Column(String(255), nullable=False, comment='模型 API 地址')
    api_key = Column(String(255), nullable=False, comment='API 密钥')
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), comment='创建时间')


class Subject(Base):
    """科目表"""
    __tablename__ = "subjects"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='科目ID')
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='所属用户 ID')
    school_id = Column(BigInteger, ForeignKey('schools.id', ondelete='SET NULL'), nullable=True, comment='所属学校ID')
    college_id = Column(BigInteger, ForeignKey('colleges.id', ondelete='SET NULL'), nullable=True, comment='所属学院ID')
    major_id = Column(BigInteger, ForeignKey('majors.id', ondelete='SET NULL'), nullable=True, comment='所属专业ID')
    name = Column(String(255), nullable=False, comment='科目名称')
    visibility_level = Column(Enum(VisibilityLevel), nullable=False, default=VisibilityLevel.private, comment='可见级别')
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), comment='创建时间')


class SubjectShare(Base):
    """科目共享表"""
    __tablename__ = "subject_shares"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='共享记录ID')
    owner_user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='科目拥有者ID')
    subject_id = Column(BigInteger, ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, comment='被共享的科目ID')
    target_user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, comment='被共享给的用户ID（NULL表示公共）')
    share_type = Column(Enum(ShareType), nullable=False, comment='共享类型：USER=指定用户，PUBLIC=公共')
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), comment='创建时间')



class Question(Base):
    """题库表"""
    __tablename__ = "questions"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='题目 ID')
    subject_id = Column(BigInteger, ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, comment='科目 ID')
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='用户 ID')
    school_id = Column(BigInteger, ForeignKey('schools.id', ondelete='SET NULL'), nullable=True, comment='所属学校ID')
    college_id = Column(BigInteger, ForeignKey('colleges.id', ondelete='SET NULL'), nullable=True, comment='所属学院ID')
    major_id = Column(BigInteger, ForeignKey('majors.id', ondelete='SET NULL'), nullable=True, comment='所属专业ID')
    type = Column(Enum(QuestionType), nullable=False, comment='题目类型')
    question = Column(Text, nullable=False, comment='题干内容')
    options_json = Column(JSON, nullable=True, comment='选项 JSON')
    answer = Column(Text, nullable=False, comment='正确答案')
    analysis = Column(Text, nullable=False, comment='解析')
    difficulty_level = Column(String(20), nullable=False, default='medium', comment='难度：easy/medium/hard')
    quality_score = Column(Integer, nullable=False, default=60, comment='题目质量分 0-100')
    knowledge_tag = Column(String(255), nullable=True, comment='知识点标签')
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), comment='创建时间')
    # 移除is_major字段，统一用type区分


class QuestionResource(Base):
    """题目资源表（图片、表格JSON、图像描述等）"""
    __tablename__ = "question_resources"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='资源ID')
    question_id = Column(BigInteger, ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, comment='关联题目ID')
    resource_type = Column(String(50), nullable=False, comment='资源类型：image/table_json/diagram_desc/other')
    resource_content = Column(Text, nullable=False, comment='资源内容：图片URL或JSON数据')
    resource_order = Column(Integer, default=0, comment='资源显示顺序')
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), comment='创建时间')
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), comment='更新时间')


class PracticeSession(Base):
    """练习会话表（扩展支持试卷练习）"""
    __tablename__ = "practice_sessions"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='练习会话 ID')
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='用户 ID')
    subject_id = Column(BigInteger, ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, comment='科目 ID')
    
    # 试卷相关字段（新增）
    session_type = Column(Enum('instant', 'paper_normal', 'paper_error', name='session_type_enum'), 
                          default='instant', comment='会话类型：instant=即时练习，paper_normal=普通试卷，paper_error=错题试卷')
    title = Column(String(255), nullable=True, comment='试卷标题（试卷模式使用）')
    duration = Column(Integer, nullable=True, comment='时长（分钟），NULL表示不限时')
    status = Column(Enum('in_progress', 'completed', 'expired', name='session_status_enum'), 
                   default='completed', comment='状态：in_progress=进行中，completed=已完成，expired=已过期')
    expires_at = Column(TIMESTAMP, nullable=True, comment='过期时间（试卷模式使用）')
    completed_at = Column(TIMESTAMP, nullable=True, comment='完成时间')
    
    # 统计字段（原有）
    total_count = Column(Integer, nullable=False, comment='总题数')
    correct_count = Column(Integer, nullable=False, comment='正确题数')
    wrong_count = Column(Integer, nullable=False, comment='错误题数')
    accuracy = Column(String(10), nullable=False, comment='正确率')
    grade = Column(String(10), nullable=False, comment='成绩等级 A/B/C/D/F')
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), comment='练习时间')


class PracticeRecord(Base):
    """练习记录表（扩展支持答案保存）"""
    __tablename__ = "practice_records"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='练习记录 ID')
    session_id = Column(BigInteger, ForeignKey('practice_sessions.id', ondelete='CASCADE'), nullable=True, comment='练习会话 ID')
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='用户 ID')
    subject_id = Column(BigInteger, ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, comment='科目 ID')
    question_id = Column(BigInteger, ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, comment='题目 ID')
    question_order = Column(Integer, nullable=True, comment='题目顺序（试卷模式使用）')
    user_answer = Column(Text, nullable=False, comment='用户作答')
    answer_images = Column(JSON, nullable=True, comment='答案图片（JSON数组，试卷模式使用）')
    is_correct = Column(Integer, nullable=False, comment='是否正确 1=正确 0=错误')
    answered_at = Column(TIMESTAMP, nullable=True, comment='作答时间（试卷模式使用）')
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), comment='作答时间')


class ErrorBook(Base):
    """错题集表"""
    __tablename__ = "error_book"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='错题记录 ID')
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='用户 ID')
    subject_id = Column(BigInteger, ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, comment='科目 ID')
    question_id = Column(BigInteger, ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, comment='题目 ID')
    wrong_count = Column(Integer, default=1, comment='累计错误次数')
    last_wrong_at = Column(TIMESTAMP, server_default=func.current_timestamp(), comment='最后错误时间')


# ============================================================
# 权限管理表
# ============================================================

class DataAccessPermission(Base):
    """数据访问权限表"""
    __tablename__ = "data_access_permissions"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='权限ID')
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='用户ID')
    resource_type = Column(Enum(ResourceType), nullable=False, comment='资源类型')
    resource_id = Column(BigInteger, nullable=False, comment='资源ID')
    permission_level = Column(Enum(PermissionLevel), nullable=False, default=PermissionLevel.read, comment='权限级别')
    granted_by = Column(BigInteger, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, comment='授权人ID')
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), comment='创建时间')
    expires_at = Column(TIMESTAMP, nullable=True, comment='过期时间（NULL表示永久）')




# ============================================================
# 资料管理相关模型
# ============================================================

class MaterialType(enum.Enum):
    """资料类型枚举"""
    textbook = "textbook"  # 教材
    note = "note"          # 笔记
    exercise = "exercise"  # 习题
    other = "other"        # 其他


class MaterialStatus(enum.Enum):
    """资料状态枚举"""
    uploading = "uploading"    # 上传中
    processing = "processing"  # 处理中
    ready = "ready"            # 就绪
    error = "error"            # 错误


class Material(Base):    
    """学习资料表"""
    __tablename__ = "materials"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False, comment="资料名称")
    file_path = Column(String(500), nullable=False, comment="MinIO文件路径")
    file_type = Column(String(50), nullable=False, comment="文件类型")
    file_size = Column(BigInteger, nullable=False, comment="文件大小（字节）")
    content_text = Column(Text, comment="提取的文本内容")
    material_type = Column(Enum(MaterialType), default=MaterialType.other, comment="资料类型")
    tags = Column(JSON, comment="标签（JSON数组）")
    question_count = Column(Integer, default=0, comment="生成的题目数")
    status = Column(Enum(MaterialStatus), default=MaterialStatus.uploading, comment="状态")
    error_message = Column(Text, comment="错误信息")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class MaterialQuestion(Base):
    """资料题目关联表"""
    __tablename__ = "material_questions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(Integer, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    confidence_score = Column(String(10), default="0.80", comment="AI生成置信度")
    generated_at = Column(TIMESTAMP, server_default=func.now())


# ============================================================
# 即时通讯系统相关模型
# ============================================================

class FriendshipStatus(enum.Enum):
    """好友状态枚举"""
    pending = "pending"      # 待确认
    accepted = "accepted"    # 已接受
    rejected = "rejected"    # 已拒绝
    blocked = "blocked"      # 已拉黑


class Friendship(Base):
    """好友关系表"""
    __tablename__ = "friendships"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    friend_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="好友ID")
    status = Column(Enum(FriendshipStatus), default=FriendshipStatus.pending, comment="状态")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class MessageType(enum.Enum):
    """消息类型枚举"""
    text = "text"      # 文本
    image = "image"    # 图片
    file = "file"      # 文件


class ChatMessage(Base):
    """聊天消息表"""
    __tablename__ = "chat_messages"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    from_user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="发送者ID")
    to_user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="接收者ID")
    content = Column(Text, nullable=False, comment="消息内容")
    message_type = Column(Enum(MessageType), default=MessageType.text, comment="消息类型")
    is_read = Column(Integer, default=0, comment="是否已读")
    read_at = Column(TIMESTAMP, nullable=True, comment="阅读时间")
    created_at = Column(TIMESTAMP, server_default=func.now())


class BlockType(enum.Enum):
    """封禁类型枚举"""
    register = "register"  # 注册
    login = "login"        # 登录
    all = "all"            # 全部


class IPBlacklist(Base):
    """IP黑名单表"""
    __tablename__ = "ip_blacklist"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ip_address = Column(String(45), nullable=False, unique=True, comment="IP地址")
    reason = Column(String(255), comment="封禁原因")
    block_type = Column(Enum(BlockType), default=BlockType.all, comment="封禁类型")
    expires_at = Column(TIMESTAMP, nullable=True, comment="过期时间")
    created_at = Column(TIMESTAMP, server_default=func.now())


class RegionBlacklist(Base):
    """区域黑名单表"""
    __tablename__ = "region_blacklist"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    region = Column(String(100), nullable=False, unique=True, comment="区域标识")
    reason = Column(String(255), comment="封禁原因")
    block_type = Column(Enum(BlockType), default=BlockType.all, comment="封禁类型")
    expires_at = Column(TIMESTAMP, nullable=True, comment="过期时间")
    created_at = Column(TIMESTAMP, server_default=func.now())


class UserOnlineStatus(Base):
    """用户在线状态表"""
    __tablename__ = "user_online_status"
    
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    is_online = Column(Integer, default=0, comment="是否在线")
    last_seen = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), comment="最后在线时间")
    socket_id = Column(String(100), comment="WebSocket连接ID")


# ============================================================
# 考试倒计时表
# ============================================================

class ExamSchedule(Base):
    """考试日程表（用于顶栏倒计时）"""
    __tablename__ = "exam_schedules"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='考试日程 ID')
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='所属用户 ID')
    subject_name = Column(String(255), nullable=False, comment='科目名称（自由填写，可与 subjects 表关联）')
    subject_id = Column(BigInteger, ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True, comment='关联科目 ID（可选）')
    exam_time = Column(TIMESTAMP, nullable=False, comment='考试时间（年月日时分）')
    exam_location = Column(String(255), nullable=True, comment='考试地点')
    note = Column(String(500), nullable=True, comment='备注')
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), comment='创建时间')
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), comment='更新时间')
