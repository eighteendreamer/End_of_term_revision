-- ============================================================================
-- 迁移：为 llm_models 增加"默认模型 / 能力标记 / 输出预算"字段
-- 日期：2026-10-29
-- 目标库：end_of_term_revision（生产请先在测试库跑一遍）
--
-- 说明：
--   * 本脚本只 ALTER，不 DROP，可安全作用于已有业务库。
--   * 不要拿 database/end_of_term_revision.sql 代替本脚本——那份初始化 SQL
--     含 DROP TABLE，导入会清掉现有题库。
--   * MySQL 的 ADD COLUMN 不幂等：重复执行会报 "Duplicate column name"，
--     属正常，说明该列已存在。执行前请先跑下面的"执行前检查"。
-- ============================================================================

-- ---------- 执行前检查：确认这些列还不存在 ----------
SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'llm_models'
ORDER BY ORDINAL_POSITION;

-- ---------- 迁移 ----------
ALTER TABLE `llm_models`
  ADD COLUMN `display_name`       varchar(255) NULL     COMMENT '展示名称，留空则用模型名称'      AFTER `api_key`,
  ADD COLUMN `is_default`         tinyint(1)   NOT NULL DEFAULT 0 COMMENT '是否为该用户的默认模型' AFTER `display_name`,
  ADD COLUMN `supports_vision`    tinyint(1)   NOT NULL DEFAULT 0 COMMENT '是否接受图片输入'       AFTER `is_default`,
  ADD COLUMN `supports_json_mode` tinyint(1)   NOT NULL DEFAULT 1 COMMENT '是否支持 response_format=json_object' AFTER `supports_vision`,
  ADD COLUMN `max_output_tokens`  int          NOT NULL DEFAULT 8192 COMMENT '单次最大输出 token 预算' AFTER `supports_json_mode`;

-- 每个用户把最早的一条设为默认，保证迁移后 get_user_llm 的选取结果
-- 与迁移前 .first() 的实际行为一致，不改变现有用户的既有表现。
UPDATE `llm_models` m
JOIN (SELECT MIN(`id`) AS min_id FROM `llm_models` GROUP BY `user_id`) t
  ON m.`id` = t.min_id
SET m.`is_default` = 1;

-- ---------- 执行后校验 ----------
SELECT `id`, `user_id`, `model_name`, `is_default`, `supports_vision`,
       `supports_json_mode`, `max_output_tokens`
FROM `llm_models`
ORDER BY `user_id`, `is_default` DESC, `id`;

-- 每个用户应恰好有一条默认模型；出现 0 条说明该用户配置为空，出现多条需手工收敛。
SELECT `user_id`, COUNT(*) AS default_rows
FROM `llm_models`
WHERE `is_default` = 1
GROUP BY `user_id`
HAVING COUNT(*) <> 1;

-- ---------- 回滚（仅在需要撤销本次迁移时执行） ----------
-- ALTER TABLE `llm_models`
--   DROP COLUMN `max_output_tokens`,
--   DROP COLUMN `supports_json_mode`,
--   DROP COLUMN `supports_vision`,
--   DROP COLUMN `is_default`,
--   DROP COLUMN `display_name`;
