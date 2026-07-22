-- ============================================================
-- 性能调优：附加覆盖索引（不改动任何表结构 / 关系 / 枚举）
-- ------------------------------------------------------------
-- 用途：加速练习统计与排行榜的聚合查询
--   SELECT user_id, COUNT(*), SUM(is_correct)
--   FROM practice_records
--   WHERE user_id = ? [AND created_at >= ?]
--   GROUP BY user_id
-- 该覆盖索引让上述聚合无需回表即可完成。
--
-- 说明：
-- 1. 仅新增索引，不删除、不修改现有表/列/外键。
-- 2. MySQL 不支持 CREATE INDEX IF NOT EXISTS，故用 information_schema 做幂等判断，
--    可安全地重复执行本脚本。
-- 3. 由 DBA / 使用者择机在目标库中手动执行。
-- ============================================================

-- practice_records: (user_id, created_at, is_correct) 覆盖统计/榜单聚合
SET @idx_exists := (
  SELECT COUNT(1)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'practice_records'
    AND index_name = 'idx_pr_user_created_correct'
);
SET @sql := IF(
  @idx_exists = 0,
  'CREATE INDEX idx_pr_user_created_correct ON practice_records (user_id, created_at, is_correct)',
  'SELECT ''idx_pr_user_created_correct already exists, skipped'' AS msg'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 其余高频组合索引（如 questions 的 subject_id/type 组合、practice_records 的
-- user_id+created_at、error_book 的 user_id+subject_id+question_id 等）现有 schema
-- 已覆盖，无需重复添加。
