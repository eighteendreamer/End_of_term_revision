/*
 Navicat Premium Dump SQL

 Source Server         : 腾讯云_MySQL
 Source Server Type    : MySQL
 Source Server Version : 90001 (9.0.1)
 Source Host           : localhost:3306
 Source Schema         : end_of_term_revision

 Target Server Type    : MySQL
 Target Server Version : 90001 (9.0.1)
 File Encoding         : 65001

 Date: 16/06/2026 13:34:50
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for chat_messages
-- ----------------------------
DROP TABLE IF EXISTS `chat_messages`;
CREATE TABLE `chat_messages`  (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `from_user_id` bigint NOT NULL COMMENT '发送者ID',
  `to_user_id` bigint NOT NULL COMMENT '接收者ID',
  `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '消息内容',
  `message_type` enum('text','image','file') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'text' COMMENT '消息类型',
  `is_read` tinyint(1) NULL DEFAULT 0 COMMENT '是否已读',
  `read_at` timestamp NULL DEFAULT NULL COMMENT '阅读时间',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_from_user`(`from_user_id` ASC) USING BTREE,
  INDEX `idx_to_user`(`to_user_id` ASC) USING BTREE,
  INDEX `idx_created_at`(`created_at` ASC) USING BTREE,
  INDEX `idx_conversation`(`from_user_id` ASC, `to_user_id` ASC, `created_at` ASC) USING BTREE,
  CONSTRAINT `chat_messages_ibfk_1` FOREIGN KEY (`from_user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `chat_messages_ibfk_2` FOREIGN KEY (`to_user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 23 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '聊天消息表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for colleges
-- ----------------------------
DROP TABLE IF EXISTS `colleges`;
CREATE TABLE `colleges`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '学院ID',
  `school_id` bigint NOT NULL COMMENT '所属学校ID',
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '学院名称',
  `code` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '学院代码',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `idx_school_name`(`school_id` ASC, `name` ASC) USING BTREE,
  INDEX `idx_school_id`(`school_id` ASC) USING BTREE,
  CONSTRAINT `colleges_ibfk_1` FOREIGN KEY (`school_id`) REFERENCES `schools` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 5 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '学院表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for data_access_permissions
-- ----------------------------
DROP TABLE IF EXISTS `data_access_permissions`;
CREATE TABLE `data_access_permissions`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '权限ID',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `resource_type` enum('subject','question') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '资源类型：subject=科目，question=题目',
  `resource_id` bigint NOT NULL COMMENT '资源ID',
  `permission_level` enum('read','write','admin') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'read' COMMENT '权限级别：read=只读，write=读写，admin=管理',
  `granted_by` bigint NULL DEFAULT NULL COMMENT '授权人ID',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `expires_at` timestamp NULL DEFAULT NULL COMMENT '过期时间（NULL表示永久）',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `idx_user_resource`(`user_id` ASC, `resource_type` ASC, `resource_id` ASC) USING BTREE,
  INDEX `idx_user_id`(`user_id` ASC) USING BTREE,
  INDEX `idx_resource`(`resource_type` ASC, `resource_id` ASC) USING BTREE,
  INDEX `idx_granted_by`(`granted_by` ASC) USING BTREE,
  CONSTRAINT `data_access_permissions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `data_access_permissions_ibfk_2` FOREIGN KEY (`granted_by`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '数据访问权限表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for db_configs
-- ----------------------------
DROP TABLE IF EXISTS `db_configs`;
CREATE TABLE `db_configs`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '数据库配置 ID',
  `user_id` bigint NOT NULL COMMENT '所属用户 ID',
  `db_host` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '数据库主机地址',
  `db_port` int NOT NULL COMMENT '数据库端口号',
  `db_user` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '数据库用户名',
  `db_password` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '数据库密码',
  `db_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '数据库名',
  `is_active` tinyint(1) NULL DEFAULT 0 COMMENT '是否是当前使用的数据库配置',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `user_id`(`user_id` ASC) USING BTREE,
  CONSTRAINT `db_configs_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '用户自定义数据库配置表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for error_book
-- ----------------------------
DROP TABLE IF EXISTS `error_book`;
CREATE TABLE `error_book`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '错题记录 ID',
  `user_id` bigint NOT NULL COMMENT '用户 ID',
  `subject_id` bigint NOT NULL COMMENT '科目 ID',
  `question_id` bigint NOT NULL COMMENT '题目 ID',
  `wrong_count` int NULL DEFAULT 1 COMMENT '累计错误次数',
  `last_wrong_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后错误时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `user_id`(`user_id` ASC, `subject_id` ASC, `question_id` ASC) USING BTREE,
  INDEX `subject_id`(`subject_id` ASC) USING BTREE,
  INDEX `question_id`(`question_id` ASC) USING BTREE,
  INDEX `idx_last_wrong_at`(`last_wrong_at` ASC) USING BTREE,
  INDEX `idx_error_book_user_subject_question`(`user_id` ASC, `subject_id` ASC, `question_id` ASC) USING BTREE,
  CONSTRAINT `error_book_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `error_book_ibfk_2` FOREIGN KEY (`subject_id`) REFERENCES `subjects` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `error_book_ibfk_3` FOREIGN KEY (`question_id`) REFERENCES `questions` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 1785 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '错题集表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for friendships
-- ----------------------------
DROP TABLE IF EXISTS `friendships`;
CREATE TABLE `friendships`  (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `friend_id` bigint NOT NULL COMMENT '好友ID',
  `status` enum('pending','accepted','rejected','blocked') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'pending' COMMENT '状态：待确认、已接受、已拒绝、已拉黑',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_user_friend`(`user_id` ASC, `friend_id` ASC) USING BTREE,
  INDEX `idx_user_id`(`user_id` ASC) USING BTREE,
  INDEX `idx_friend_id`(`friend_id` ASC) USING BTREE,
  INDEX `idx_status`(`status` ASC) USING BTREE,
  CONSTRAINT `friendships_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `friendships_ibfk_2` FOREIGN KEY (`friend_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 3 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '好友关系表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for ip_blacklist
-- ----------------------------
DROP TABLE IF EXISTS `ip_blacklist`;
CREATE TABLE `ip_blacklist`  (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `ip_address` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'IP地址（支持IPv6）',
  `reason` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '封禁原因',
  `block_type` enum('register','login','all') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'all' COMMENT '封禁类型',
  `expires_at` timestamp NULL DEFAULT NULL COMMENT '过期时间（NULL表示永久）',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_ip`(`ip_address` ASC) USING BTREE,
  INDEX `idx_expires_at`(`expires_at` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 770 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = 'IP黑名单表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for llm_models
-- ----------------------------
DROP TABLE IF EXISTS `llm_models`;
CREATE TABLE `llm_models`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '模型配置 ID',
  `user_id` bigint NOT NULL COMMENT '所属用户 ID',
  `model_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '模型名称',
  `base_url` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '模型 API 地址',
  `api_key` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'API 密钥',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `user_id`(`user_id` ASC) USING BTREE,
  CONSTRAINT `llm_models_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 4 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '用户自定义大模型配置表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for majors
-- ----------------------------
DROP TABLE IF EXISTS `majors`;
CREATE TABLE `majors`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '专业ID',
  `college_id` bigint NOT NULL COMMENT '所属学院ID',
  `school_id` bigint NOT NULL COMMENT '所属学校ID（冗余字段，便于查询）',
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '专业名称',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `idx_college_name`(`college_id` ASC, `name` ASC) USING BTREE,
  INDEX `idx_college_id`(`college_id` ASC) USING BTREE,
  INDEX `idx_school_id`(`school_id` ASC) USING BTREE,
  CONSTRAINT `majors_ibfk_1` FOREIGN KEY (`college_id`) REFERENCES `colleges` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `majors_ibfk_2` FOREIGN KEY (`school_id`) REFERENCES `schools` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 6 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '专业表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for material_questions
-- ----------------------------
DROP TABLE IF EXISTS `material_questions`;
CREATE TABLE `material_questions`  (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `material_id` bigint NOT NULL COMMENT '资料ID',
  `question_id` bigint NOT NULL COMMENT '题目ID',
  `confidence_score` decimal(3, 2) NULL DEFAULT 0.80 COMMENT 'AI生成置信度（0-1）',
  `generated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_material_question`(`material_id` ASC, `question_id` ASC) USING BTREE,
  INDEX `idx_material`(`material_id` ASC) USING BTREE,
  INDEX `idx_question`(`question_id` ASC) USING BTREE,
  CONSTRAINT `material_questions_ibfk_1` FOREIGN KEY (`material_id`) REFERENCES `materials` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `material_questions_ibfk_2` FOREIGN KEY (`question_id`) REFERENCES `questions` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '资料题目关联表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for materials
-- ----------------------------
DROP TABLE IF EXISTS `materials`;
CREATE TABLE `materials`  (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `subject_id` bigint NOT NULL COMMENT '科目ID',
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '资料名称',
  `file_path` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'MinIO文件路径',
  `file_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '文件类型（pdf/docx/txt/jpg/png）',
  `file_size` bigint NOT NULL COMMENT '文件大小（字节）',
  `content_text` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '提取的文本内容',
  `material_type` enum('textbook','note','exercise','other') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'other' COMMENT '资料类型',
  `tags` json NULL COMMENT '标签（JSON数组）',
  `question_count` int NULL DEFAULT 0 COMMENT '生成的题目数',
  `status` enum('uploading','processing','ready','error') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'uploading' COMMENT '状态',
  `error_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '错误信息',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_user_subject`(`user_id` ASC, `subject_id` ASC) USING BTREE,
  INDEX `idx_status`(`status` ASC) USING BTREE,
  INDEX `idx_created_at`(`created_at` ASC) USING BTREE,
  INDEX `materials_ibfk_2`(`subject_id` ASC) USING BTREE,
  CONSTRAINT `materials_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `materials_ibfk_2` FOREIGN KEY (`subject_id`) REFERENCES `subjects` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '学习资料表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for practice_records
-- ----------------------------
DROP TABLE IF EXISTS `practice_records`;
CREATE TABLE `practice_records`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '练习记录 ID',
  `session_id` bigint NULL DEFAULT NULL COMMENT '练习会话 ID',
  `user_id` bigint NOT NULL COMMENT '用户 ID',
  `subject_id` bigint NOT NULL COMMENT '科目 ID',
  `question_id` bigint NOT NULL COMMENT '题目 ID',
  `question_order` int NULL DEFAULT NULL COMMENT '题目顺序（试卷模式使用）',
  `user_answer` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '用户作答',
  `answer_images` json NULL COMMENT '答案图片（JSON数组，试卷模式使用）',
  `is_correct` tinyint(1) NOT NULL COMMENT '是否正确 1=正确 0=错误',
  `answered_at` timestamp NULL DEFAULT NULL COMMENT '作答时间（试卷模式使用）',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作答时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `user_id`(`user_id` ASC) USING BTREE,
  INDEX `subject_id`(`subject_id` ASC) USING BTREE,
  INDEX `question_id`(`question_id` ASC) USING BTREE,
  INDEX `idx_session_id`(`session_id` ASC) USING BTREE,
  INDEX `idx_user_subject`(`user_id` ASC, `subject_id` ASC) USING BTREE,
  INDEX `idx_created_at`(`created_at` ASC) USING BTREE,
  INDEX `idx_user_time`(`user_id` ASC, `created_at` ASC) USING BTREE,
  INDEX `idx_session_question`(`session_id` ASC, `question_id` ASC) USING BTREE,
  INDEX `idx_practice_records_user_subject_question`(`user_id` ASC, `subject_id` ASC, `question_id` ASC) USING BTREE,
  INDEX `idx_practice_records_subject_question_correct`(`subject_id` ASC, `question_id` ASC, `is_correct` ASC) USING BTREE,
  INDEX `idx_practice_records_session_question`(`session_id` ASC, `question_id` ASC) USING BTREE,
  CONSTRAINT `practice_records_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `practice_records_ibfk_3` FOREIGN KEY (`subject_id`) REFERENCES `subjects` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `practice_records_ibfk_4` FOREIGN KEY (`question_id`) REFERENCES `questions` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 15381 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '练习记录表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for practice_sessions
-- ----------------------------
DROP TABLE IF EXISTS `practice_sessions`;
CREATE TABLE `practice_sessions`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '练习会话 ID',
  `user_id` bigint NOT NULL COMMENT '用户 ID',
  `subject_id` bigint NOT NULL COMMENT '科目 ID',
  `session_type` enum('instant','paper_normal','paper_error') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'instant' COMMENT '会话类型：instant=即时练习，paper_normal=普通试卷，paper_error=错题试卷',
  `source_type` enum('manual','material') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'manual' COMMENT '来源类型：manual=手动创建，material=资料生成',
  `source_materials` json NULL COMMENT '来源资料ID列表（JSON数组）',
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '试卷标题（试卷模式使用）',
  `duration` int NULL DEFAULT NULL COMMENT '时长（分钟），NULL表示不限时',
  `status` enum('in_progress','completed','expired') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'completed' COMMENT '状态：in_progress=进行中，completed=已完成，expired=已过期',
  `expires_at` timestamp NULL DEFAULT NULL COMMENT '过期时间（试卷模式使用）',
  `completed_at` timestamp NULL DEFAULT NULL COMMENT '完成时间',
  `total_count` int NOT NULL COMMENT '总题数',
  `correct_count` int NOT NULL COMMENT '正确题数',
  `wrong_count` int NOT NULL COMMENT '错误题数',
  `accuracy` decimal(5, 2) NOT NULL COMMENT '正确率',
  `grade` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '成绩等级 A/B/C/D/F',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '练习时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_user_subject`(`user_id` ASC, `subject_id` ASC) USING BTREE,
  INDEX `idx_created_at`(`created_at` ASC) USING BTREE,
  INDEX `practice_sessions_ibfk_2`(`subject_id` ASC) USING BTREE,
  INDEX `idx_user_time`(`user_id` ASC, `created_at` ASC) USING BTREE,
  INDEX `idx_user_status`(`user_id` ASC, `status` ASC) USING BTREE,
  INDEX `idx_session_type`(`session_type` ASC) USING BTREE,
  INDEX `idx_expires`(`expires_at` ASC) USING BTREE,
  INDEX `idx_practice_sessions_user_subject_type_created`(`user_id` ASC, `subject_id` ASC, `session_type` ASC, `created_at` ASC) USING BTREE,
  CONSTRAINT `practice_sessions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `practice_sessions_ibfk_2` FOREIGN KEY (`subject_id`) REFERENCES `subjects` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 390 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '练习会话表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for question_resources
-- ----------------------------
DROP TABLE IF EXISTS `question_resources`;
CREATE TABLE `question_resources`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '资源ID',
  `question_id` bigint NOT NULL COMMENT '关联题目ID',
  `resource_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '资源类型：image/table_json/diagram_desc/other',
  `resource_content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '资源内容：图片URL或JSON数据',
  `resource_order` int NULL DEFAULT 0 COMMENT '资源显示顺序',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_question_id`(`question_id` ASC) USING BTREE,
  INDEX `idx_resource_type`(`resource_type` ASC) USING BTREE,
  CONSTRAINT `question_resources_ibfk_1` FOREIGN KEY (`question_id`) REFERENCES `questions` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '题目资源表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for questions
-- ----------------------------
DROP TABLE IF EXISTS `questions`;
CREATE TABLE `questions`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '题目 ID',
  `subject_id` bigint NOT NULL COMMENT '科目 ID',
  `user_id` bigint NOT NULL COMMENT '用户 ID',
  `school_id` bigint NULL DEFAULT NULL COMMENT '所属学校ID',
  `college_id` bigint NULL DEFAULT NULL COMMENT '所属学院ID',
  `major_id` bigint NULL DEFAULT NULL COMMENT '所属专业ID',
  `type` enum('single','multiple','judge','fill','major') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '题目类型',
  `question` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '题干内容',
  `options_json` json NULL COMMENT '选项 JSON',
  `answer` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '正确答案',
  `analysis` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '解析',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `is_deleted` tinyint(1) NULL DEFAULT 0 COMMENT '是否已删除（0=正常，1=已删除）',
  `difficulty_level` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'medium' COMMENT '难度：easy/medium/hard',
  `quality_score` int NOT NULL DEFAULT 60 COMMENT '题目质量分 0-100',
  `knowledge_tag` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '知识点标签',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `subject_id`(`subject_id` ASC) USING BTREE,
  INDEX `user_id`(`user_id` ASC) USING BTREE,
  INDEX `idx_type`(`type` ASC) USING BTREE,
  INDEX `idx_created_at`(`created_at` ASC) USING BTREE,
  INDEX `idx_subject_type`(`subject_id` ASC, `type` ASC) USING BTREE,
  INDEX `idx_user_subject`(`user_id` ASC, `subject_id` ASC) USING BTREE,
  INDEX `idx_updated_at`(`updated_at` ASC) USING BTREE,
  INDEX `idx_is_deleted`(`is_deleted` ASC) USING BTREE,
  INDEX `idx_subject_updated`(`subject_id` ASC, `updated_at` ASC) USING BTREE,
  INDEX `idx_school_id`(`school_id` ASC) USING BTREE,
  INDEX `idx_college_id`(`college_id` ASC) USING BTREE,
  INDEX `idx_major_id`(`major_id` ASC) USING BTREE,
  INDEX `idx_questions_subject_type_difficulty`(`subject_id` ASC, `type` ASC, `difficulty_level` ASC) USING BTREE,
  INDEX `idx_questions_subject_type_quality`(`subject_id` ASC, `type` ASC, `quality_score` ASC) USING BTREE,
  CONSTRAINT `questions_ibfk_1` FOREIGN KEY (`subject_id`) REFERENCES `subjects` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `questions_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `questions_ibfk_college` FOREIGN KEY (`college_id`) REFERENCES `colleges` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `questions_ibfk_major` FOREIGN KEY (`major_id`) REFERENCES `majors` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `questions_ibfk_school` FOREIGN KEY (`school_id`) REFERENCES `schools` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 1683 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '题库表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for region_blacklist
-- ----------------------------
DROP TABLE IF EXISTS `region_blacklist`;
CREATE TABLE `region_blacklist`  (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `region` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '区域标识（如：CN-BJ-HD）',
  `reason` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '封禁原因',
  `block_type` enum('register','login','all') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'all' COMMENT '封禁类型',
  `expires_at` timestamp NULL DEFAULT NULL COMMENT '过期时间（NULL表示永久）',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_region`(`region` ASC) USING BTREE,
  INDEX `idx_expires_at`(`expires_at` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '区域黑名单表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for schools
-- ----------------------------
DROP TABLE IF EXISTS `schools`;
CREATE TABLE `schools`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '学校ID',
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '学校名称',
  `code` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '学校代码',
  `province` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '省份',
  `city` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '城市',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `idx_name`(`name` ASC) USING BTREE,
  INDEX `idx_code`(`code` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 5 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '学校表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for subject_shares
-- ----------------------------
DROP TABLE IF EXISTS `subject_shares`;
CREATE TABLE `subject_shares`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '共享记录ID',
  `owner_user_id` bigint NOT NULL COMMENT '科目拥有者ID',
  `subject_id` bigint NOT NULL COMMENT '被共享的科目ID',
  `target_user_id` bigint NULL DEFAULT NULL COMMENT '被共享给的用户ID（NULL表示公共共享）',
  `share_type` enum('USER','PUBLIC') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '共享类型：USER=指定用户，PUBLIC=公共',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `unique_share`(`subject_id` ASC, `target_user_id` ASC, `share_type` ASC) USING BTREE,
  INDEX `idx_subject_id`(`subject_id` ASC) USING BTREE,
  INDEX `idx_target_user`(`target_user_id` ASC) USING BTREE,
  INDEX `idx_owner`(`owner_user_id` ASC) USING BTREE,
  CONSTRAINT `subject_shares_ibfk_1` FOREIGN KEY (`owner_user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `subject_shares_ibfk_2` FOREIGN KEY (`subject_id`) REFERENCES `subjects` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `subject_shares_ibfk_3` FOREIGN KEY (`target_user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 18 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '科目共享表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for subjects
-- ----------------------------
DROP TABLE IF EXISTS `subjects`;
CREATE TABLE `subjects`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '科目ID',
  `user_id` bigint NOT NULL COMMENT '所属用户 ID',
  `school_id` bigint NULL DEFAULT NULL COMMENT '所属学校ID',
  `college_id` bigint NULL DEFAULT NULL COMMENT '所属学院ID',
  `major_id` bigint NULL DEFAULT NULL COMMENT '所属专业ID',
  `visibility_level` enum('private','major','college','school','public') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'private' COMMENT '可见级别：private=私有，major=专业级，college=学院级，school=校级，public=公开',
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '科目名称',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `name`(`name` ASC, `user_id` ASC) USING BTREE,
  INDEX `user_id`(`user_id` ASC) USING BTREE,
  INDEX `idx_name`(`name` ASC) USING BTREE,
  INDEX `idx_school_id`(`school_id` ASC) USING BTREE,
  INDEX `idx_college_id`(`college_id` ASC) USING BTREE,
  INDEX `idx_major_id`(`major_id` ASC) USING BTREE,
  INDEX `idx_visibility`(`visibility_level` ASC) USING BTREE,
  CONSTRAINT `subjects_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `subjects_ibfk_college` FOREIGN KEY (`college_id`) REFERENCES `colleges` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `subjects_ibfk_major` FOREIGN KEY (`major_id`) REFERENCES `majors` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `subjects_ibfk_school` FOREIGN KEY (`school_id`) REFERENCES `schools` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 15 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '科目表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for user_online_status
-- ----------------------------
DROP TABLE IF EXISTS `user_online_status`;
CREATE TABLE `user_online_status`  (
  `user_id` bigint NOT NULL,
  `is_online` tinyint(1) NULL DEFAULT 0 COMMENT '是否在线',
  `last_seen` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后在线时间',
  `socket_id` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT 'WebSocket连接ID',
  PRIMARY KEY (`user_id`) USING BTREE,
  CONSTRAINT `user_online_status_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '用户在线状态表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '用户主键 ID',
  `student_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '学号（唯一，用于登录）',
  `school_id` bigint NULL DEFAULT NULL COMMENT '所属学校ID',
  `college_id` bigint NULL DEFAULT NULL COMMENT '所属学院ID',
  `major_id` bigint NULL DEFAULT NULL COMMENT '所属专业ID',
  `username` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '用户名',
  `password_hash` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '密码哈希值（加密存储）',
  `class_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '班级',
  `gender` enum('male','female','hidden') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '性别：male=男，female=女，hidden=隐藏',
  `profile_completed` int NULL DEFAULT 0 COMMENT '账号信息是否完善：0=未完善，1=已完善',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `unique_student_id`(`student_id` ASC) USING BTREE,
  INDEX `idx_school_id`(`school_id` ASC) USING BTREE,
  INDEX `idx_college_id`(`college_id` ASC) USING BTREE,
  INDEX `idx_major_id`(`major_id` ASC) USING BTREE,
  CONSTRAINT `users_ibfk_major` FOREIGN KEY (`major_id`) REFERENCES `majors` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `users_ibfk_school` FOREIGN KEY (`school_id`) REFERENCES `schools` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 64 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '系统用户表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- View structure for v_question_full_info
-- ----------------------------
DROP VIEW IF EXISTS `v_question_full_info`;
CREATE ALGORITHM = UNDEFINED SQL SECURITY DEFINER VIEW `v_question_full_info` AS select `q`.`id` AS `id`,`q`.`subject_id` AS `subject_id`,`sub`.`name` AS `subject_name`,`q`.`user_id` AS `user_id`,`u`.`username` AS `owner_name`,`q`.`type` AS `type`,`q`.`question` AS `question`,`q`.`school_id` AS `school_id`,`s`.`name` AS `school_name`,`q`.`college_id` AS `college_id`,`col`.`name` AS `college_name`,`q`.`major_id` AS `major_id`,`m`.`name` AS `major_name`,`q`.`created_at` AS `created_at` from (((((`questions` `q` join `subjects` `sub` on((`q`.`subject_id` = `sub`.`id`))) join `users` `u` on((`q`.`user_id` = `u`.`id`))) left join `schools` `s` on((`q`.`school_id` = `s`.`id`))) left join `colleges` `col` on((`q`.`college_id` = `col`.`id`))) left join `majors` `m` on((`q`.`major_id` = `m`.`id`)));

-- ----------------------------
-- View structure for v_subject_full_info
-- ----------------------------
DROP VIEW IF EXISTS `v_subject_full_info`;
CREATE ALGORITHM = UNDEFINED SQL SECURITY DEFINER VIEW `v_subject_full_info` AS select `sub`.`id` AS `id`,`sub`.`name` AS `name`,`sub`.`user_id` AS `user_id`,`u`.`username` AS `owner_name`,`sub`.`school_id` AS `school_id`,`s`.`name` AS `school_name`,`sub`.`college_id` AS `college_id`,`col`.`name` AS `college_name`,`sub`.`major_id` AS `major_id`,`m`.`name` AS `major_name`,`sub`.`visibility_level` AS `visibility_level`,`sub`.`created_at` AS `created_at` from ((((`subjects` `sub` join `users` `u` on((`sub`.`user_id` = `u`.`id`))) left join `schools` `s` on((`sub`.`school_id` = `s`.`id`))) left join `colleges` `col` on((`sub`.`college_id` = `col`.`id`))) left join `majors` `m` on((`sub`.`major_id` = `m`.`id`)));

-- ----------------------------
-- View structure for v_user_full_info
-- ----------------------------
DROP VIEW IF EXISTS `v_user_full_info`;
CREATE ALGORITHM = UNDEFINED SQL SECURITY DEFINER VIEW `v_user_full_info` AS select `u`.`id` AS `id`,`u`.`student_id` AS `student_id`,`u`.`username` AS `username`,`u`.`school_id` AS `school_id`,`s`.`name` AS `school_name`,`u`.`college_id` AS `college_id`,`c`.`name` AS `college_name`,`u`.`major_id` AS `major_id`,`m`.`name` AS `major_name`,`u`.`class_name` AS `class_name`,`u`.`gender` AS `gender`,`u`.`profile_completed` AS `profile_completed`,`u`.`created_at` AS `created_at` from (((`users` `u` left join `schools` `s` on((`u`.`school_id` = `s`.`id`))) left join `colleges` `c` on((`u`.`college_id` = `c`.`id`))) left join `majors` `m` on((`u`.`major_id` = `m`.`id`)));

-- ----------------------------
-- Procedure structure for sp_check_subject_access
-- ----------------------------
DROP PROCEDURE IF EXISTS `sp_check_subject_access`;
delimiter ;;
CREATE PROCEDURE `sp_check_subject_access`(IN p_user_id BIGINT,
  IN p_subject_id BIGINT,
  OUT p_has_access BOOLEAN)
BEGIN
  DECLARE v_owner_id BIGINT;
  DECLARE v_visibility VARCHAR(20);
  DECLARE v_subject_school_id BIGINT;
  DECLARE v_subject_college_id BIGINT;
  DECLARE v_subject_major_id BIGINT;
  DECLARE v_user_school_id BIGINT;
  DECLARE v_user_college_id BIGINT;
  DECLARE v_user_major_id BIGINT;
  
  -- 获取科目信息
  SELECT user_id, visibility_level, school_id, college_id, major_id
  INTO v_owner_id, v_visibility, v_subject_school_id, v_subject_college_id, v_subject_major_id
  FROM subjects
  WHERE id = p_subject_id;
  
  -- 获取用户信息
  SELECT school_id, college_id, major_id
  INTO v_user_school_id, v_user_college_id, v_user_major_id
  FROM users
  WHERE id = p_user_id;
  
  -- 检查权限
  SET p_has_access = FALSE;
  
  -- 1. 如果是所有者，直接有权限
  IF v_owner_id = p_user_id THEN
    SET p_has_access = TRUE;
  -- 2. 如果是公开的，所有人都有权限
  ELSEIF v_visibility = 'public' THEN
    SET p_has_access = TRUE;
  -- 3. 如果是校级共享，同校用户有权限
  ELSEIF v_visibility = 'school' AND v_user_school_id = v_subject_school_id THEN
    SET p_has_access = TRUE;
  -- 4. 如果是学院级共享，同学院用户有权限
  ELSEIF v_visibility = 'college' AND v_user_college_id = v_subject_college_id THEN
    SET p_has_access = TRUE;
  -- 5. 如果是专业级共享，同专业用户有权限
  ELSEIF v_visibility = 'major' AND v_user_major_id = v_subject_major_id THEN
    SET p_has_access = TRUE;
  -- 6. 检查是否有特殊授权
  ELSEIF EXISTS (
    SELECT 1 FROM data_access_permissions
    WHERE user_id = p_user_id
      AND resource_type = 'subject'
      AND resource_id = p_subject_id
      AND (expires_at IS NULL OR expires_at > NOW())
  ) THEN
    SET p_has_access = TRUE;
  END IF;
END
;;
delimiter ;

-- ----------------------------
-- Triggers structure for table questions
-- ----------------------------
DROP TRIGGER IF EXISTS `questions_before_update`;
delimiter ;;
CREATE TRIGGER `questions_before_update` BEFORE UPDATE ON `questions` FOR EACH ROW BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END
;;
delimiter ;

SET FOREIGN_KEY_CHECKS = 1;
