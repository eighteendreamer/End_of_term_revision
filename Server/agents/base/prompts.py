# -*- coding: utf-8 -*-
"""
Agent 专用提示词 — 扩展现有 Prompt.py
"""
from langchain_core.prompts import ChatPromptTemplate

# ============================================================
# 文本导入 Agent 提示词
# ============================================================

TEXT_PARSE_SYSTEM = "你是一个专业的答案解析助手，擅长将文本转换为结构化的题目数据。"

TEXT_PARSE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", TEXT_PARSE_SYSTEM),
    ("user", """请将以下文本解析成标准的题目格式。

文本内容：
{text}

科目：{subject}

{format_instructions}

注意事项：
1. type 只能是：single（单选）、multiple（多选）、judge（判断）、fill（填空题）、major（大型题）
2. 判断题的 options 为 ["对", "错"]，答案只能是 "对" 或 "错"
3. 填空题的 options 可以为空数组 []
4. 如果文本中没有答案，请根据题目内容生成正确答案
5. 如果文本中没有解析，请根据题目内容生成详细解析，并写出关键计算步骤
6. 必须从文本中尽量识别出所有题目，禁止返回 "questions": []
7. 文本通常为试卷或复习题，带有编号 1.、2.、(1)、(2) 等，请根据这些编号拆分成多道题目
8. 当题干中出现"_____""（ ）"等空格，需要填写一个或多个数值、概率、函数表达式等明确答案时，即使需要一定计算步骤，也统一使用填空题 type="fill"
9. 只有当题目要求书写较长的推导过程、证明、论述或综合分析时，才使用大型题 type="major"，options 使用 []
10. 大型题必须是主观题，analysis 必须给出分步推导过程
11. 对于 single/multiple 题，options 中每一项必须包含完整的选项内容

**数学/物理公式要求：**
- 所有数学公式和物理公式必须使用 LaTeX 格式
- 行内公式使用 $...$ 包裹，如：已知函数 $f(x)=x^2+2x+1$
- 独立公式使用 $$...$$ 包裹，如：$$\\int_0^1 x^2 dx = \\frac{{1}}{{3}}$$
- 必须保留完整的 LaTeX 语法（分式、上下标、希腊字母、积分、根号等）
- 禁止将公式转换为自然语言描述
""")
])


# ============================================================
# 文件导入 Agent 提示词
# ============================================================

FILE_OCR_VERIFY_SYSTEM = (
    "你是一个专业的文档校验专家。你的任务是对比 OCR 结果和原始文件文本，"
    "找出 OCR 可能遗漏或错误的内容。"
)

FILE_OCR_VERIFY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", FILE_OCR_VERIFY_SYSTEM),
    ("user", """OCR 识别结果（Markdown）：
{ocr_markdown}

原始文件文本（参考基准）：
{reference_text}

请仔细对比两份文本，输出校验报告 JSON：
{{
  "issues": [
    {{
      "type": "missing_question|formula_error|option_missing|table_error|other",
      "description": "问题描述",
      "location": "大致位置",
      "severity": "high|medium|low"
    }}
  ],
  "question_count_ocr": 数字,
  "question_count_reference": 数字,
  "overall_quality": "high|medium|low"
}}

注意：
1. missing_question: OCR 可能遗漏了某些题目，对比参考文本找出遗漏的
2. formula_error: OCR 对数学公式还原能力有限，检查公式是否不完整或格式错误
3. option_missing: 检查选择题选项是否完整
4. 如果参考文本为空或质量很差，以 OCR 结果为准
5. 所有数学公式使用 LaTeX 格式
""")
])

FORMULA_REPRODUCE_SYSTEM = (
    "你是一个专业的数学/物理文档工程师。"
    "你的任务是将文档中的数学公式和图表用代码精确复现。"
)

FORMULA_REPRODUCE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", FORMULA_REPRODUCE_SYSTEM),
    ("user", """请从以下内容中识别并复现所有数学公式和图表：

OCR 文本：
{ocr_text}

校验报告中指出的公式/图表问题：
{verify_issues}

请逐个复现，输出 JSON：
{{
  "items": [
    {{
      "type": "latex",
      "content": "LaTeX 公式",
      "description": "公式描述"
    }},
    {{
      "type": "code",
      "content": "Python matplotlib 代码",
      "description": "图表描述"
    }}
  ]
}}

**公式复现规则：**
- 所有数学公式使用 LaTeX 格式，行内 $...$，独立 $$...$$
- 完整保留 LaTeX 语法：\\frac, \\int, \\sum, \\sqrt, \\alpha 等

**图表复现规则：**
- 对于数学图画（函数图像、几何图形、坐标系等），生成 Python matplotlib 代码
- 代码必须可直接运行，使用 plt.savefig() 保存，不要 plt.show()
- 坐标轴标注、网格线、图例等要完整
- 图片尺寸 (6, 4)，dpi=150
""")
])

FILE_STRUCTURE_SYSTEM = (
    "你是一个专业的答案解析专家。"
    "请将 OCR 解析的文档内容结构化为标准题目格式。"
    "你会收到三份输入：OCR 结果、校验报告、公式/图表复现结果。"
    "请综合三者，输出最准确的题目 JSON。"
)

FILE_STRUCTURE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", FILE_STRUCTURE_SYSTEM),
    ("user", """科目：{subject}

OCR 解析结果（Markdown）：
{ocr_markdown}

校验报告：
{verify_report}

公式/图表复现结果：
{reproduce_result}

{format_instructions}

注意：
1. 公式请优先使用复现结果中的 LaTeX
2. 图表代码请存入对应题目的 resources 字段
3. 所有数学公式使用 LaTeX 格式
4. type 只能是：single/multiple/judge/fill/major
5. 判断题 options 为 ["对", "错"]
6. 填空题和大型题 options 为空数组
7. 必须尽量识别出所有题目
8. 对于 single/multiple 题，options 必须包含完整选项内容
""")
])


# ============================================================
# 图片导入 Agent 提示词
# ============================================================

IMAGE_VISION_SYSTEM = (
    "你是一个专业的题目识别专家。"
    "请仔细观察图片中的题目内容，识别并解析出所有题目。"
)

IMAGE_VISION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", IMAGE_VISION_SYSTEM),
    ("user", [
        {"type": "image_url", "image_url": "{image_url}"},
        {"type": "text", "text": """科目：{subject}

请识别所有题目，{format_instructions}

注意事项：
1. 仔细识别题目类型：single/multiple/judge/fill/major
2. 判断题的 options 为 ["对", "错"]，答案只能是 "对" 或 "错"
3. 填空题的 options 可以为空数组 []
4. 如果图片中包含答案，请使用图片中的答案；如果没有答案，请根据题目内容生成正确答案
5. 必须生成详细的答案解析，说明为什么这个答案是正确的，并写出关键计算步骤
6. 确保题目内容、选项、答案完整准确，不要出现乱码或遗漏
7. 必须尽量识别出所有题目，禁止返回 "questions": []
8. 试卷通常带有题号，请依据题号拆分成多道题目
9. 所有数学公式和物理公式必须使用 LaTeX 格式
   - 行内公式使用 $...$ 包裹
   - 独立公式使用 $$...$$ 包裹
   - 必须保留完整的 LaTeX 语法
10. 对于 single/multiple 题，options 中每一项必须包含完整的选项内容
"""}
    ])
])

IMAGE_VERIFY_SYSTEM = (
    "你是一个图片题目识别校验专家。"
    "你将收到两种解析结果：Vision 模型直接解析的题目 JSON 和 OCR 提取的文本。"
    "请对比两者，找出差异并输出最终校正确认的结果。"
)

IMAGE_VERIFY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", IMAGE_VERIFY_SYSTEM),
    ("user", """Vision 模型解析结果：
{vision_result}

OCR 提取文本：
{ocr_text}

科目：{subject}

请对比校验，{format_instructions}

重点关注：
1. 题目数量是否一致，取并集
2. 公式是否准确（以 OCR 文本中的 LaTeX 为参考修正 Vision 结果）
3. 选项和答案是否完整，补全缺失信息
4. 去重：内容相同的题目只保留信息更完整的一份
5. 所有数学公式使用 LaTeX 格式
""")
])


# ============================================================
# 结构化预处理提示词（复用现有 Prompt.py 的内容）
# ============================================================

STRUCTURED_PARSE_SYSTEM = (
    "你是一个专业的题目处理助手，擅长为预处理的题目补充答案和解析。"
)

STRUCTURED_PARSE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", STRUCTURED_PARSE_SYSTEM),
    ("user", """你是题目处理专家。我已经使用正则表达式预处理了文档，提取了题号和题型信息。
现在请你为每道题补充正确答案、详细解析，并在必要时修正题型。

预处理结果：
{structured_data}

科目：{subject}

请严格按照以下 JSON 格式输出（必须是有效的 JSON）：
{{
  "subject": "{subject}",
  "questions": [
    {{
      "type": "题型（single/multiple/judge/fill/major，可修正预处理结果）",
      "question": "题干内容",
      "options": ["选项数组"],
      "answer": "正确答案",
      "analysis": "详细解析"
    }}
  ]
}}

注意事项：
1. 如果预处理检测到的题型置信度 >= 0.85，优先使用该题型
2. 如果置信度 < 0.85 或为 unknown，请根据题目内容确定正确题型
3. type 只能是：single、multiple、judge、fill、major
4. 判断题 options 必须为 ["对", "错"]，答案只能是 "对" 或 "错"
5. 填空题和大型题的 options 使用空数组 []
6. 单选/多选题必须包含完整选项
7. 如果原文中包含答案，请使用原文答案；如果没有，请生成正确答案
8. 必须生成详细的答案解析
9. 所有数学公式和物理公式必须使用 LaTeX 格式
10. 如果遇到仅包含 "判断题"、"选择题" 等标题的条目，请忽略该条目
11. 必须返回有效的 JSON 格式，不要包含任何其他文字
""")
])
