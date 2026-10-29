# -*- coding: utf-8 -*-
"""
llm_models 的列定义同时写在四个地方，这里把它们钉成一致。

  1. SQLAlchemy 模型 Server/database/models.py —— 运行时真正用的
  2. 增量迁移 database/migrations/2026-10-29_llm_models_capabilities.sql —— 存量库
  3. 初始化 SQL database/end_of_term_revision.sql 的 CREATE TABLE —— 新建库/重装
  4. 兜底常量 services/llm_config_service.DEFAULT_MAX_OUTPUT_TOKENS

任一处漂移在开发机上都看不出来：模型多写一列而初始化 SQL 没补，
用 dump 重建出来的库一打开「AI 模型配置」就是 Unknown column 500。
所以这里做文本级 round-trip 校验，不靠人记。
"""
import io
import os
import re
import sys
import unittest

SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SERVER_ROOT)
if SERVER_ROOT not in sys.path:
    sys.path.insert(0, SERVER_ROOT)

from database.models import LLMModel
from services import llm_config_service

INIT_SQL = os.path.join(REPO_ROOT, "database", "end_of_term_revision.sql")
MIGRATION = os.path.join(REPO_ROOT, "database", "migrations",
                         "2026-10-29_llm_models_capabilities.sql")

# 本轮为"改三个字段就能换模型"新增的能力列；加列/减列都要同时改三处
NEW_COLUMNS = ("display_name", "is_default", "supports_vision",
               "supports_json_mode", "max_output_tokens")


def _read(path: str) -> str:
    with io.open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _normalize(definition: str) -> str:
    definition = re.sub(r"COMMENT\s+'[^']*'", "", definition)
    definition = re.sub(r"CHARACTER SET \S+|COLLATE \S+", "", definition)
    # 去掉 COMMENT 后会在逗号前留下空格，不归一的话两处"看起来一样"的定义会判为不同
    definition = re.sub(r"\s+", " ", definition).strip().lower()
    return definition.rstrip(" ,")


def _ddl_columns(sql: str, table: str) -> dict:
    """CREATE TABLE 段里的 列名 -> 类型与默认值。"""
    start = sql.index("CREATE TABLE `%s`" % table)
    block = sql[start:sql.index("\n) ENGINE", start)]
    columns = {}
    for line in block.splitlines():
        match = re.match(r"\s+`(\w+)`\s+(.+)$", line)
        if match:
            columns[match.group(1)] = _normalize(match.group(2))
    return columns


def _migrated_columns(sql: str) -> dict:
    """迁移脚本 ADD COLUMN 的 列名 -> 类型与默认值。"""
    body = re.sub(r"^--.*$", "", sql, flags=re.MULTILINE)
    pattern = r"ADD COLUMN\s+`(\w+)`\s+(.*?)(?=\s+AFTER\s|\s*,\s*$|\s*;\s*$)"
    return {name: _normalize(definition)
            for name, definition in re.findall(pattern, body, flags=re.MULTILINE)}


class TestLlmModelSchemaContract(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.orm_columns = [column.name for column in LLMModel.__table__.columns]
        cls.init_sql = _read(INIT_SQL)
        cls.migration = _read(MIGRATION)
        cls.declared = _ddl_columns(cls.init_sql, "llm_models")
        cls.added = _migrated_columns(cls.migration)

    def test_init_sql_declares_every_column_the_model_uses(self):
        missing = [name for name in self.orm_columns if name not in self.declared]
        self.assertEqual(missing, [],
                         "初始化 SQL 的 llm_models 缺列：用它重建的库会在读取模型配置时报 Unknown column")

    def test_migration_columns_exist_in_the_baseline_and_match_types(self):
        self.assertEqual(sorted(self.added), sorted(NEW_COLUMNS))
        for name, definition in self.added.items():
            self.assertIn(name, self.declared, f"{name} 只写进了迁移，没写进建表语句")
            self.assertEqual(self.declared[name], definition,
                             f"{name} 在迁移与建表语句里的类型/默认值不一致")

    def test_boolean_columns_are_tinyint_one(self):
        """SQLAlchemy 的 Boolean 落到 MySQL 是 tinyint(1)；写成 int 会改变读回的值域。"""
        for column in LLMModel.__table__.columns:
            if column.type.__class__.__name__ != "Boolean":
                continue
            self.assertIn("tinyint(1)", self.declared[column.name], column.name)

    def test_string_lengths_match_the_orm(self):
        for column in LLMModel.__table__.columns:
            length = getattr(column.type, "length", None)
            if length:
                self.assertIn("varchar(%d)" % length, self.declared[column.name],
                              column.name)

    def test_default_output_budget_is_one_number_in_all_four_places(self):
        fallback = llm_config_service.DEFAULT_MAX_OUTPUT_TOKENS
        orm_default = int(LLMModel.__table__.columns["max_output_tokens"]
                          .server_default.arg.text)
        self.assertEqual(orm_default, fallback)
        for label, definition in (("初始化 SQL", self.declared["max_output_tokens"]),
                                   ("迁移脚本", self.added["max_output_tokens"])):
            self.assertIn("default %d" % fallback, definition,
                          f"{label} 的 max_output_tokens 默认值与代码兜底值不一致")

    def test_migration_is_additive_only(self):
        """存量库脚本绝不能带 DROP，否则会连着题库一起没。"""
        body = re.sub(r"^--.*$", "", self.migration, flags=re.MULTILINE)
        self.assertNotIn("DROP TABLE", body.upper())
        self.assertNotIn("DROP COLUMN", body.upper())
        self.assertNotIn("DELETE FROM", body.upper())


if __name__ == "__main__":
    unittest.main(verbosity=2)
