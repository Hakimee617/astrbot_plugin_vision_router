"""Vision Router —— 为纯文本 LLM 提供视觉能力（类似 dsh-vision-router）

功能：
- 自动识别消息中的图片，调用可识图的视觉模型 API（OpenAI 兼容格式）
- 把图片描述作为机器人回复发送，让纯文本模型“看到”图片内容
- 支持触发模式：auto（自动）/ command（指令触发）/ both（两者）
- 支持任意 OpenAI 兼容视觉端点：Qwen-VL、GLM-4V、GPT-4o、DeepSeek-V4-Flash-Vision 等

作者：Firefly
"""

import asyncio
import base64
import os
from pathlib import Path

import httpx

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.event.filter import EventMessageType
from astrbot.api.message_components import Image, Plain
from astrbot.api.star import Context, Star

DEFAULT_PROMPT = "请详细描述这张图片的内容，包括主体、场景、文字、风格等，用中文回答。"


class VisionRouterPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        config = config or {}
        self.enabled = config.get("enabled", True)
        self.api_base = (config.get("api_base") or "").strip().rstrip("/")
        self.api_key = (config.get("api_key") or "").strip()
        self.model = (config.get("model") or "qwen-vl-max").strip()
        self.trigger_mode = config.get("trigger_mode", "auto")  # auto / command / both
        self.command = (config.get("command") or "/看图").strip()
        self.prompt = (config.get("prompt") or DEFAULT_PROMPT).strip()
        self.reply_prefix = (config.get("reply_prefix") or "【识图】").strip()
        self.timeout = int(config.get("timeout", 60))
        self.max_retries = int(config.get("max_retries", 2))
        self.show_typing = bool(config.get("show_typing", True))

        if not self.api_key:
            logger.warning("[vision_router] 未配置 api_key，插件将处于休眠状态。请在 WebUI 插件设置中填写。")

    # ---------- 工具函数 ----------

    @staticmethod
    def _file_to_data_url(path: str) -> str | None:
        """本地文件转 base64 data URL"""
        ext = Path(path).suffix.lower().lstrip(".")
        mime = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp",
        }.get(ext, "image/jpeg")
        try:
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return f"data:{mime};base64,{b64}"
        except Exception as e:
            logger.error(f"[vision_router] 读取图片失败 {path}: {e}")
            return None

    async def _extract_images(self, event: AstrMessageEvent) -> list[str]:
        """从消息链中提取图片（返回 URL 或 data URL 列表）"""
        images: list[str] = []
        for comp in event.get_messages():
            if not isinstance(comp, Image):
                continue
            url = (comp.url or "").strip()
            file = (comp.file or "").strip()
            path = (comp.path or "").strip()
            src = None
            if url.startswith("http://") or url.startswith("https://"):
                src = url
            elif file.startswith("http://") or file.startswith("https://"):
                src = file
            elif path and os.path.exists(path):
                src = self._file_to_data_url(path)
            elif file.startswith("file://"):
                fp = file[7:]
                if os.path.exists(fp):
                    src = self._file_to_data_url(fp)
            if src:
                images.append(src)
        return images

    async def _call_vision_api(self, image_src: str, prompt: str) -> str:
        """调用 OpenAI 兼容的视觉模型 API"""
        url = f"{self.api_base}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_src}},
                    ],
                }
            ],
            "temperature": 0.3,
            "max_tokens": 1024,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

    # ---------- 事件处理 ----------

    @filter.event_message_type(EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听消息：识别图片 → 调用视觉 API → 回复描述"""
        if not self.enabled:
            return
        if not self.api_key or not self.api_base:
            return

        msg = (event.get_message_str() or "").strip()
        is_command = msg.startswith(self.command)

        # 触发模式判断
        if self.trigger_mode == "command" and not is_command:
            return

        images = await self._extract_images(event)
        if not images:
            return

        # 指令后跟的文本可作为自定义提示词（command 模式）
        prompt = self.prompt
        if is_command:
            custom = msg[len(self.command):].strip()
            if custom:
                prompt = custom

        logger.info(f"[vision_router] 收到 {len(images)} 张图片，调用 {self.model} 识图...")

        # 可选：发送“正在识图”提示
        if self.show_typing:
            yield event.chain_result([Plain("🔍 正在识图，请稍候...")])

        # 逐张识图（最多处理全部图片）
        results = []
        for img in images:
            desc = None
            for attempt in range(self.max_retries + 1):
                try:
                    desc = await self._call_vision_api(img, prompt)
                    break
                except Exception as e:
                    logger.error(f"[vision_router] 识图失败(第{attempt + 1}次): {e}")
                    if attempt < self.max_retries:
                        await asyncio.sleep(1.5)
            results.append(desc if desc else "（识图失败）")

        if len(results) == 1:
            reply = f"{self.reply_prefix}{results[0]}"
        else:
            parts = [f"{self.reply_prefix}共 {len(results)} 张图片："]
            for i, r in enumerate(results, 1):
                parts.append(f"\n[{i}] {r}")
            reply = "".join(parts)

        yield event.chain_result([Plain(reply)])
