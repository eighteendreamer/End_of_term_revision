# -*- coding: utf-8 -*-
"""
百度 Unlimited-OCR API 客户端
支持 PDF 和图片的文档解析，输出 Markdown + JSON
"""
import base64
import os
import time
import requests
from typing import Optional, Dict, Any


class UnlimitedOCRClient:
    """
    百度 Unlimited-OCR 异步 API 封装

    使用流程:
    1. 获取 access_token
    2. 提交文档解析任务 (返回 task_id)
    3. 轮询任务状态
    4. 下载 Markdown 和 JSON 结果
    """

    BASE_URL = "https://aip.baidubce.com"
    TOKEN_URL = f"{BASE_URL}/oauth/2.0/token"
    TASK_URL = f"{BASE_URL}/rest/2.0/brain/online/v2/unlimited-ocr-parser/task"
    QUERY_URL = f"{BASE_URL}/rest/2.0/brain/online/v2/unlimited-ocr-parser/task/query"

    def __init__(self, api_key: str, secret_key: str):
        """
        :param api_key: 百度 AI 平台 API Key
        :param secret_key: 百度 AI 平台 Secret Key
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self._access_token: Optional[str] = None

    def _get_access_token(self) -> str:
        """获取百度 API access_token（带缓存）"""
        if self._access_token:
            return self._access_token

        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key,
        }
        resp = requests.get(self.TOKEN_URL, params=params, timeout=30)
        data = resp.json()
        if "access_token" not in data:
            raise RuntimeError(
                f"获取 access_token 失败: {data.get('error', '未知错误')}"
            )
        self._access_token = data["access_token"]
        return self._access_token

    def parse_document(self, file_path: str,
                       max_wait: int = 180,
                       poll_interval: int = 5) -> Dict[str, Any]:
        """
        解析文档（PDF/图片），返回 OCR 结果

        :param file_path: 文件路径
        :param max_wait: 最大等待秒数
        :param poll_interval: 轮询间隔秒数
        :return: {
            "markdown": str,           # Markdown 格式的解析结果
            "parse_result": dict,     # JSON 格式的解析结果（含坐标等）
            "raw": dict               # 原始 API 返回
        }
        :raises RuntimeError: OCR 提交或解析失败
        :raises TimeoutError: OCR 解析超时
        """
        token = self._get_access_token()

        # 1. 提交任务
        with open(file_path, "rb") as f:
            file_data = base64.b64encode(f.read()).decode()

        submit_url = f"{self.TASK_URL}?access_token={token}"
        resp = requests.post(
            submit_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "file_data": file_data,
                "file_name": os.path.basename(file_path),
            },
            timeout=120,
        )
        result = resp.json()

        if result.get("error_code"):
            raise RuntimeError(
                f"OCR 提交失败: {result.get('error_msg', '未知错误')} "
                f"(code: {result.get('error_code')})"
            )

        task_id = result.get("result", {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"OCR 提交返回异常: {result}")

        print(f"[UnlimitedOCR] 任务已提交, task_id={task_id}")

        # 2. 轮询获取结果
        query_url = f"{self.QUERY_URL}?access_token={token}"
        elapsed = 0
        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            resp = requests.post(
                query_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={"task_id": task_id},
                timeout=60,
            )
            status_data = resp.json()
            status = status_data.get("result", {}).get("status", "")

            if status == "success":
                md_url = status_data["result"]["markdown_url"]
                json_url = status_data["result"]["parse_result_url"]

                markdown = requests.get(md_url, timeout=60).text
                parse_result = requests.get(json_url, timeout=60).json()

                print(f"[UnlimitedOCR] 解析完成, "
                      f"Markdown 长度: {len(markdown)}")
                return {
                    "markdown": markdown,
                    "parse_result": parse_result,
                    "raw": status_data,
                }

            elif status == "failed":
                error = status_data["result"].get("task_error", "未知错误")
                raise RuntimeError(f"OCR 解析失败: {error}")

            print(f"[UnlimitedOCR] 等待中... 状态: {status}, "
                  f"已等待 {elapsed}s")

        raise TimeoutError(f"OCR 解析超时 ({max_wait}s)")

    def parse_image(self, image_path: str,
                    max_wait: int = 60) -> Dict[str, Any]:
        """解析图片（复用 parse_document）"""
        return self.parse_document(image_path, max_wait=max_wait)


def create_ocr_client(api_key: str, secret_key: str) -> UnlimitedOCRClient:
    """创建 OCR 客户端实例"""
    return UnlimitedOCRClient(api_key, secret_key)
