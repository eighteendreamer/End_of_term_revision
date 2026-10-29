# -*- coding: utf-8 -*-
r"""
真机梯度自验工具 —— 把"入库题数 = 原文题数"这条验收线变成一条命令。

为什么单独有这个脚本：验收要记录请求批次数、每批 finish_reason、修复器命中
次数、逐题解析失败数、入库题数与原文题数差。这些数据只有连上真实模型才拿得到，
离线测试只能证明"代码在假模型下守恒"。

本脚本不读数据库、不入库、不打印 api_key；输入只有你指定的那一个文件。
它复用生产用的同一套链路（import_limits 校验 → 整页渲染 → QuestionImportAgent），
所以这里跑出来的数字就是页面导入会得到的数字。

文本档（题数可精确控制，原文题数由代码给出，可直接判 PASS/FAIL）：

    $env:GRADIENT_API_KEY="sk-..."
    python scripts/import_gradient.py --base-url https://xx/v1 --model 模型名 `
      --subject 数学 --text-file "..\测试用的材料\xxx.txt" --tiers 5,20,50

文档档（整页交视觉模型，本地不做文本提取，原文题数只能人工数，按 --pages 顺序逐档给）：

    python scripts/import_gradient.py --base-url https://xx/v1 --model 视觉模型名 `
      --subject 数学 --file "..\测试用的材料\文档\2026年高考数学试卷（全国2卷）.docx" `
      --pages 1,2 --expect 6,19

退出码：0 全部档题数守恒；1 至少一档不守恒；2 配置或输入本身被拒。
"""
import argparse
import io
import os
import re
import sys

SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVER_ROOT not in sys.path:
    sys.path.insert(0, SERVER_ROOT)

from agents.question_import_agent import QuestionImportAgent
from services import import_limits
from services.document_renderer import RendererUnavailable, render_to_images
from services.llm_client import LLMClient, LLMUnavailable
from services.question_chunker import split_blocks
from services.question_schema import parse_questions

_PAGE_RE = re.compile(r"第\s*(\d+)\s*页")
_FIRST_NUMBER_RE = re.compile(r"^\s*(\d{1,3})[.、]", re.MULTILINE)


class RecordingClient(LLMClient):
    """生产客户端的子类，只多做一件事：把每批的预算与 finish_reason 记下来。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = []

    def complete_json(self, system, user, max_tokens, images=None):
        result = super().complete_json(system, user, max_tokens, images=images)
        parsed = parse_questions(result.text)
        self.calls.append({
            "tag": "%d.%s" % (len(self.calls) + 1, _batch_tag(user)),
            "max_tokens": max_tokens,
            "finish_reason": result.finish_reason,
            "json_mode": "JSON模式" if result.json_mode_used else "已降级",
            "attempts": result.attempts,
            "returned": len(parsed["questions"]),
            "dropped": parsed["dropped"],
            "truncated": result.truncated or parsed["truncated"],
            "repairs": len(parsed["repairs"]),
            "mode": parsed["parse_mode"],
        })
        return result


def _batch_tag(user: str) -> str:
    """从提示词里认出这批是哪一页/从哪题开始，报告里能对上原文。"""
    page = _PAGE_RE.search(user)
    if page:
        return "第%s页" % page.group(1)
    body = user.split("输出要求：")[0]
    number = _FIRST_NUMBER_RE.search(body)
    return "题%s起" % number.group(1) if number else "未标注"


def _read_text(path: str) -> str:
    with io.open(path, "r", encoding="utf-8", errors="strict") as handle:
        return handle.read()


def _print_calls(client: RecordingClient) -> None:
    print("\n  每批模型调用（%d 次）" % len(client.calls))
    print("  %-9s %7s %-13s %-8s %4s %4s %4s %4s %-8s" %
          ("批次", "预算", "finish_reason", "JSON模式", "返回", "丢题", "修复",
           "重试", "解析方式"))
    for call in client.calls:
        print("  %-9s %7d %-13s %-8s %4d %4d %4d %4d %-8s" % (
            call["tag"], call["max_tokens"], call["finish_reason"], call["json_mode"],
            call["returned"], call["dropped"], call["repairs"], call["attempts"],
            call["mode"]))


def _report(label: str, source: int, outcome, client: RecordingClient) -> bool:
    stats = outcome.as_dict()["stats"]
    _print_calls(client)
    gap = source - outcome.count
    print("\n  原文 %d 题 → 解析 %d 题 | 差 %d | 请求 %d 批(重试 %d) | "
          "丢题 %d | 缺题 %d | 修复器命中 %d 类 | 疑点 %d 题"
          % (source, outcome.count, gap, stats["batches"], stats["retried_batches"],
             stats["dropped"], stats["missing"], len(stats["repairs"]),
             len(outcome.issues)))
    for line in stats["errors"]:
        print("    错误：%s" % line)
    for repair in stats["repairs"]:
        print("    修复：%s" % repair)
    passed = gap == 0 and not stats["missing"] and not stats["truncated"]
    print("  [%s] %s" % ("PASS 题数守恒" if passed else "FAIL 题数不守恒", label))
    return passed


def run_text_tiers(factory, subject: str, path: str, tiers):
    """返回 True/False；None 表示一档都没判成，不能当成通过。"""
    blocks = split_blocks(_read_text(path))
    if not blocks:
        print("题号切分结果为空，这个文件不适合做文本梯度。")
        return None
    print("文本共切出 %d 道题" % len(blocks))
    verdict = None
    for tier in tiers:
        if tier > len(blocks):
            print("\n[跳过] %d 题档：原文只切出 %d 题" % (tier, len(blocks)))
            continue
        text = import_limits.check_text(
            "\n\n".join(block.text for block in blocks[:tier]), field="文本")
        source = len(split_blocks(text))
        client = factory()
        print("\n===== 文本档 %d 题（实际送 %d 题，%d 字符）=====" %
              (tier, source, len(text)))
        passed = _report("%d 题档" % tier, source,
                         QuestionImportAgent(client).import_text(text, subject), client)
        verdict = passed if verdict is None else (verdict and passed)
    return verdict


def run_page_tiers(factory, subject: str, path: str, pages, expects):
    data = _read_bytes(path)
    import_limits.check_document(os.path.basename(path), data)
    images = [page.data_url() for page in render_to_images(path)]
    print("整页渲染出 %d 页" % len(images))
    verdict = None
    for index, count in enumerate(pages):
        if count > len(images):
            print("\n[跳过] 前 %d 页：文档只有 %d 页" % (count, len(images)))
            continue
        expect = expects[index] if index < len(expects) else None
        client = factory()
        print("\n===== 文档档 前 %d 页 =====" % count)
        outcome = QuestionImportAgent(client).import_images(images[:count], subject)
        if expect is None:
            _print_calls(client)
            print("\n  解析 %d 题。文档档本地不提取文本，没有可比对的原文题数；"
                  "按 --pages 的顺序补上 --expect（如 --expect 6,12）才能判定守恒。"
                  % outcome.count)
            for line in outcome.as_dict()["stats"]["errors"]:
                print("    错误：%s" % line)
            continue
        passed = _report("前 %d 页" % count, expect, outcome, client)
        verdict = passed if verdict is None else (verdict and passed)
    return verdict


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="导入链路真机梯度自验")
    parser.add_argument("--base-url", required=True, help="OpenAI 兼容端点")
    parser.add_argument("--model", required=True, help="模型名")
    parser.add_argument("--subject", default="数学")
    parser.add_argument("--api-key-env", default="GRADIENT_API_KEY",
                        help="读取密钥的环境变量名（默认 GRADIENT_API_KEY）")
    parser.add_argument("--text-file", help="纯文本题源，按题数跑梯度")
    parser.add_argument("--tiers", default="5,20,50", help="文本档题数，逗号分隔")
    parser.add_argument("--file", help="PDF/Word 题源，按页跑梯度（需视觉模型）")
    parser.add_argument("--pages", default="1,2", help="文档档页数，逗号分隔")
    parser.add_argument("--expect", default="",
                        help="与 --pages 逐档对应的原文实际题数，如 6,12")
    parser.add_argument("--max-output-tokens", type=int, default=8192)
    parser.add_argument("--no-json-mode", action="store_true",
                        help="端点不支持 response_format 时使用")
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env, "")
    if not api_key:
        print("缺少密钥：先设置环境变量 %s（脚本不会回显它的值）" % args.api_key_env)
        return 2

    def factory():
        return RecordingClient(args.base_url, api_key, args.model,
                               supports_json_mode=not args.no_json_mode,
                               max_output_tokens=args.max_output_tokens)

    try:
        if args.text_file:
            tiers = [int(x) for x in args.tiers.split(",") if x.strip()]
            verdict = run_text_tiers(factory, args.subject, args.text_file, tiers)
        elif args.file:
            pages = [int(x) for x in args.pages.split(",") if x.strip()]
            expects = [int(x) for x in args.expect.split(",") if x.strip()]
            verdict = run_page_tiers(factory, args.subject, args.file,
                                     pages, expects)
        else:
            print("要么给 --text-file，要么给 --file。")
            return 2
    except import_limits.InputRejected as exc:
        print("输入被限制拒绝：%s" % exc)
        return 2
    except RendererUnavailable as exc:
        print("服务器/本机缺少渲染组件：%s" % exc)
        return 2
    except LLMUnavailable as exc:
        print("模型调用失败：%s" % exc)
        print("这一步已经证明凭据或端点有问题，请先在页面上把模型配置跑通。")
        return 2

    if verdict is None:
        print("\n未判定：没有任何一档拿到原文题数，不能算通过。")
        return 2
    print("\n结论：%s" % ("全部参与判定的档都题数守恒" if verdict else "存在丢题档"))
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
