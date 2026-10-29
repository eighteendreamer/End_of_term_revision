# -*- coding: utf-8 -*-
"""
导入链路底座回归测试（解析、分块、输入限制）。

运行（在 Server/ 目录下）：
    python tests/test_import_foundation.py
    pytest tests/test_import_foundation.py
"""
import json
import os
import sys
import unittest

SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVER_ROOT not in sys.path:
    sys.path.insert(0, SERVER_ROOT)

from services import import_limits, question_chunker, question_schema
from utils import json_repair


class TestJsonRepair(unittest.TestCase):
    """模型输出的四类典型破损。"""

    def test_plain_json_untouched(self):
        raw = '{"subject": "数学", "questions": [{"type": "single"}]}'
        obj, repairs, err = json_repair.loads_lenient(raw)
        self.assertIsNone(err)
        self.assertEqual(repairs, [])
        self.assertEqual(obj["subject"], "数学")

    def test_code_fence_stripped(self):
        raw = "```json\n{\"subject\": \"物理\", \"questions\": []}\n```"
        obj, repairs, err = json_repair.loads_lenient(raw)
        self.assertIsNone(err)
        self.assertIn("strip_code_fence", repairs)
        self.assertEqual(obj["subject"], "物理")

    def test_prose_around_json_sliced(self):
        raw = "好的，解析结果如下：\n{\"subject\": \"化学\", \"questions\": []}\n希望有帮助。"
        obj, repairs, err = json_repair.loads_lenient(raw)
        self.assertIsNone(err, repairs)
        self.assertEqual(obj["subject"], "化学")

    def test_bare_newline_inside_string(self):
        raw = '{"subject": "数学", "analysis": "第一步\n第二步"}'
        obj, repairs, err = json_repair.loads_lenient(raw)
        self.assertIsNone(err, repairs)
        self.assertIn("escape_control_chars", repairs)
        self.assertEqual(obj["analysis"], "第一步\n第二步")

    def test_latex_single_backslash(self):
        raw = '{"subject": "数学", "question": "$\\frac{1}{3}$ 与 $\\alpha$"}'
        obj, repairs, err = json_repair.loads_lenient(raw)
        self.assertIsNone(err, repairs)
        self.assertIn("fix_invalid_escapes", repairs)
        self.assertIn("\\alpha", obj["question"])

    def test_truncated_tail_closed(self):
        raw = ('{"subject": "数学", "questions": ['
               '{"type": "single", "question": "甲"}, {"type": "fill"')
        obj, repairs, err = json_repair.loads_lenient(raw)
        self.assertIsNotNone(obj, (repairs, err))
        self.assertIn("close_truncated", repairs)
        self.assertEqual(len(obj["questions"]), 1)

    def test_per_item_recovery_keeps_good_drops_broken(self):
        raw = ('{"subject": "数学", "questions": ['
               '{"type": "single", "question": "第一题", "answer": "A"},'
               '{"type": "fill", "question": "第二题", "answer": "1"},'
               '{"type": "judge", "question": "第三题被截断')
        items, dropped = json_repair.iter_question_objects(raw)
        self.assertEqual(len(items), 2)
        self.assertEqual(dropped, 1)
        self.assertEqual([i["question"] for i in items], ["第一题", "第二题"])

    def test_empty_response_reported(self):
        obj, repairs, err = json_repair.loads_lenient("")
        self.assertIsNone(obj)
        self.assertEqual(err, "空响应")


class TestQuestionSchema(unittest.TestCase):

    def test_type_aliases_normalized(self):
        for raw_type, expected in [("选择题", "single"), ("判断题", "judge"),
                                   ("多选题", "multiple"), ("计算题", "major"),
                                   ("single", "single")]:
            q, _ = question_schema.normalize_question({
                "type": raw_type, "question": "示例题干内容",
                "options": ["A. 甲", "B. 乙", "C. 丙", "D. 丁"],
                "answer": "A", "analysis": "因为甲",
            })
            self.assertIsNotNone(q, raw_type)
            self.assertEqual(q["type"], expected, raw_type)

    def test_type_inferred_from_options(self):
        q, issues = question_schema.normalize_question({
            "question": "下列正确的是", "options": ["A. 甲", "B. 乙"], "answer": "A",
        })
        self.assertEqual(q["type"], "single")
        self.assertTrue(any("推断" in i for i in issues))

    def test_type_inferred_from_blank(self):
        q, _ = question_schema.normalize_question({
            "question": "已知 $f(x)=x^2$，则 $f(1)=$ _____", "answer": "1",
        })
        self.assertEqual(q["type"], "fill")
        self.assertEqual(q["options"], [])

    def test_judge_forces_options_and_answer(self):
        q, _ = question_schema.normalize_question({
            "type": "judge", "question": "正方形是菱形。", "answer": "√",
        })
        self.assertEqual(q["options"], ["对", "错"])
        self.assertEqual(q["answer"], "对")

    def test_multiple_answer_sorted_deduped(self):
        q, _ = question_schema.normalize_question({
            "type": "multiple", "question": "选出正确的",
            "options": ["A. 甲", "B. 乙", "C. 丙"], "answer": "C,A,B,A",
        })
        self.assertEqual(q["answer"], "A,B,C")

    def test_options_dict_becomes_ordered_list(self):
        q, _ = question_schema.normalize_question({
            "type": "single", "question": "示例",
            "options": {"A": "甲", "B": "乙", "C": "丙", "D": "丁"},
            "answer": "B",
        })
        self.assertEqual(q["options"], ["A. 甲", "B. 乙", "C. 丙", "D. 丁"])

    def test_answer_body_remapped_to_letter(self):
        q, _ = question_schema.normalize_question({
            "type": "single", "question": "示例",
            "options": ["A. 甲", "B. 乙"], "answer": "乙",
        })
        self.assertEqual(q["answer"], "B")

    def test_missing_analysis_flagged_not_fatal(self):
        q, issues = question_schema.normalize_question({
            "type": "single", "question": "示例", "options": ["A. 甲", "B. 乙"],
            "answer": "A",
        })
        self.assertIsNotNone(q)
        self.assertIn("解析缺失", issues)

    def test_question_without_stem_dropped(self):
        q, issues = question_schema.normalize_question({"type": "single", "answer": "A"})
        self.assertIsNone(q)
        self.assertEqual(issues, ["缺题干"])

    def test_parse_questions_full_mode(self):
        raw = json.dumps({
            "subject": "英语",
            "questions": [{"type": "single", "question": "题干",
                           "options": ["A. a", "B. b"], "answer": "A",
                           "analysis": "解析"}],
        }, ensure_ascii=False)
        result = question_schema.parse_questions(raw)
        self.assertEqual(result["parse_mode"], "full")
        self.assertEqual(result["subject"], "英语")
        self.assertEqual(len(result["questions"]), 1)
        self.assertEqual(result["dropped"], 0)

    def test_parse_questions_reports_truncation(self):
        raw = ('{"subject": "数学", "questions": ['
               '{"type": "single", "question": "甲题", "options": ["A. 一", "B. 二"],'
               ' "answer": "A", "analysis": "解析"},'
               '{"type": "fill", "question": "乙题被截断')
        result = question_schema.parse_questions(raw)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["questions"]), 1)
        self.assertEqual(result["questions"][0]["question"], "甲题")

    def test_parse_questions_per_item_mode(self):
        # 数组里混进一个非对象 token：整体解不通，但逐题能救回前面的完整题
        raw = ('{"subject": "数学", "questions": ['
               '{"type": "single", "question": "甲题", "options": ["A. 一", "B. 二"],'
               ' "answer": "A", "analysis": "解析"},'
               '{"type": "fill", "question": "乙题", "answer": "2", "analysis": "因为"},'
               '此处模型吐了一段说明文字]}')
        result = question_schema.parse_questions(raw)
        self.assertEqual(result["parse_mode"], "per_item")
        self.assertEqual(len(result["questions"]), 2)
        self.assertEqual([q["question"] for q in result["questions"]], ["甲题", "乙题"])

    def test_parse_questions_failed_mode_carries_reason(self):
        result = question_schema.parse_questions("模型输出了一段完全不是 JSON 的话。")
        self.assertEqual(result["parse_mode"], "failed")
        self.assertTrue(result.get("error"))
        self.assertEqual(result["questions"], [])


class TestChunker(unittest.TestCase):

    def test_splits_on_primary_numbers_only(self):
        text = ("注意事项：考试时间 90 分钟。\n一、选择题\n"
                "1. 甲？\nA. 一 B. 二\n2. 乙？\n（1）小问一\n（2）小问二\n3. 丙？")
        blocks = question_chunker.split_blocks(text)
        self.assertEqual([b.number for b in blocks], ["1", "2", "3"])
        self.assertIn("考试时间", blocks[0].text)
        self.assertIn("小问二", blocks[1].text)
        self.assertNotIn("小问二", blocks[2].text)

    def test_batch_packing_respects_question_cap(self):
        blocks = [question_chunker.QuestionBlock(str(i), f"{i}. 题干内容")
                  for i in range(1, 21)]
        batches = question_chunker.pack_batches(blocks, max_questions=8)
        self.assertEqual([b.size for b in batches], [8, 8, 4])

    def test_batch_packing_respects_token_cap(self):
        big = [question_chunker.QuestionBlock(str(i), f"{i}. " + "长" * 3000)
               for i in range(1, 6)]
        batches = question_chunker.pack_batches(big, max_questions=8,
                                                max_input_tokens=6000)
        self.assertGreater(len(batches), 1)
        self.assertEqual(sum(b.size for b in batches), 5)

    def test_split_batch_halves(self):
        batch = question_chunker.Batch(
            [question_chunker.QuestionBlock(str(i), "x") for i in range(4)])
        self.assertEqual([h.size for h in question_chunker.split_batch(batch)], [2, 2])

    def test_estimate_tokens_grows_with_length(self):
        self.assertLess(question_chunker.estimate_tokens("短"),
                        question_chunker.estimate_tokens("长" * 500))


class TestImportLimits(unittest.TestCase):

    def test_rejects_oversized_text(self):
        with self.assertRaises(import_limits.InputRejected):
            import_limits.check_text("字" * (import_limits.MAX_TEXT_CHARS + 1))

    def test_rejects_empty_text(self):
        with self.assertRaises(import_limits.InputRejected):
            import_limits.check_text("   ")

    def test_accepts_legacy_doc(self):
        self.assertEqual(
            import_limits.check_document("试卷.doc",
                                         import_limits._OLE_MAGIC + b"\x00" * 100), ".doc")

    def test_rejects_doc_that_is_not_ole(self):
        with self.assertRaises(import_limits.InputRejected):
            import_limits.check_document("试卷.doc", b"%PDF-1.4\n")

    def test_rejects_rtf(self):
        with self.assertRaises(import_limits.InputRejected):
            import_limits.check_document("试卷.rtf", b"{\\rtf1")

    def test_detects_ole_disguised_as_docx(self):
        with self.assertRaises(import_limits.InputRejected) as ctx:
            import_limits.check_document("试卷.docx",
                                         import_limits._OLE_MAGIC + b"\x00" * 100)
        self.assertIn("doc", str(ctx.exception))

    def test_accepts_real_docx(self):
        self.assertEqual(
            import_limits.check_document("a.docx", b"PK\x03\x04" + b"\x00" * 100), ".docx")

    def test_rejects_fake_image(self):
        with self.assertRaises(import_limits.InputRejected):
            import_limits.check_image(b"not an image at all")

    def test_downsamples_large_image(self):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (4000, 3000), "white").save(buf, format="PNG")
        out = import_limits.check_image(buf.getvalue())
        with Image.open(io.BytesIO(out)) as im:
            self.assertLessEqual(max(im.size), import_limits.MAX_IMAGE_EDGE)

    def test_small_image_passes_through(self):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (600, 800), "white").save(buf, format="PNG")
        self.assertEqual(import_limits.check_image(buf.getvalue()), buf.getvalue())


class TestRealSamplesFitLimits(unittest.TestCase):
    """
    阈值必须容得下用户真实导入的东西，否则限制本身就成了新的"导入不全"。

    样本目录是用户自己放的（未纳入版本库），没有就跳过。断言的是"不被拒"，
    顺带把"理科卷正文里根本没有公式"这条设计依据钉成可执行检查，
    而不是只写注释。
    """

    MATERIALS = os.path.join(os.path.dirname(SERVER_ROOT), "测试用的材料")

    def _files(self, *exts):
        found = []
        for root, _dirs, names in os.walk(self.MATERIALS):
            for name in sorted(names):
                if name.lower().endswith(exts):
                    found.append(os.path.join(root, name))
        return found

    def _read(self, path: str) -> bytes:
        with open(path, "rb") as handle:
            return handle.read()

    def test_screenshots_pass_image_checks_unchanged(self):
        if not os.path.isdir(self.MATERIALS):
            self.skipTest("缺少测试材料目录")
        images = self._files(".png", ".jpg", ".jpeg", ".webp")
        self.assertTrue(images, "材料目录下没有图片样本")
        for path in images:
            prepared = import_limits.check_image(self._read(path))
            self.assertLessEqual(len(prepared), import_limits.MAX_IMAGE_BYTES)

    def test_real_papers_pass_document_checks(self):
        if not os.path.isdir(self.MATERIALS):
            self.skipTest("缺少测试材料目录")
        docs = self._files(".docx", ".pdf")
        self.assertTrue(docs, "材料目录下没有文档样本")
        for path in docs:
            raw = self._read(path)
            self.assertEqual(
                import_limits.check_document(os.path.basename(path), raw),
                os.path.splitext(path)[1].lower())

    def test_real_paper_page_counts_stay_under_the_page_limit(self):
        """页数上限若低于真实卷子的页数，文件导入会整份被拒。"""
        if not os.path.isdir(self.MATERIALS):
            self.skipTest("缺少测试材料目录")
        import re
        import zipfile
        seen = 0
        for path in self._files(".docx"):
            try:
                with zipfile.ZipFile(path) as zf:
                    app = zf.read("docProps/app.xml").decode("utf-8", "ignore")
            except (KeyError, zipfile.BadZipFile):
                continue
            match = re.search(r"<Pages>(\d+)</Pages>", app)
            if not match:
                continue
            seen += 1
            self.assertLessEqual(
                int(match.group(1)), import_limits.MAX_PDF_PAGES,
                f"{os.path.basename(path)} 有 {match.group(1)} 页，会被页数上限拒掉")
        if not seen:
            self.skipTest("样本里读不到页数信息")

    def test_stem_papers_have_formulas_that_local_text_cannot_yield(self):
        """
        数学/化学/物理卷：公式是 OLE 对象，正文文本里没有。

        这条就是"文件导入必须整页渲染送视觉模型"的证据；哪天不再成立
        （比如试卷改用 OMML），才谈得上回到本地提取。
        """
        if not os.path.isdir(self.MATERIALS):
            self.skipTest("缺少测试材料目录")
        import re
        import zipfile
        checked = 0
        for path in self._files(".docx"):
            name = os.path.basename(path)
            if not any(subj in name for subj in ("数学", "化学", "物理")):
                continue
            with zipfile.ZipFile(path) as zf:
                doc = zf.read("word/document.xml").decode("utf-8", "ignore")
            ole = len(re.findall(r"<w:object\b", doc))
            body = re.sub(r"<[^>]+>", "", doc)
            self.assertGreater(ole, 0, f"{name} 应当含 OLE 公式对象")
            self.assertLess(len(body), import_limits.MAX_TEXT_CHARS)
            # 正文只有几千字符却有上百个公式，说明公式不在文本里
            self.assertLess(len(body), 8000, f"{name} 正文字符异常，需复核提取策略")
            checked += 1
        self.assertGreaterEqual(checked, 1, "材料里没有理科卷样本")


if __name__ == "__main__":
    unittest.main(verbosity=2)
