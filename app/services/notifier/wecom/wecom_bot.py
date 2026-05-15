# -*- coding: utf-8 -*-
"""
企业微信 Webhook 机器人通知器

简单版本，使用 .env 配置的固定 Webhook Key
"""

from typing import Optional

import httpx

from app.config import get_settings
from app.services.notifier.base import BaseNotifier

logger = __import__('logging').getLogger(__name__)


class WeComNotifier(BaseNotifier):
    """
    企业微信机器人通知器

    使用 Webhook 方式发送消息
    支持:
    - 文本消息
    - Markdown消息
    - 图片消息
    - 图文消息

    配置:
    - 在企业微信群中添加机器人
    - 获取 Webhook Key
    - 配置到 .env 文件
    """

    def __init__(self, webhook_key: Optional[str] = None):
        self.settings = get_settings()
        self.webhook_key = webhook_key or self.settings.wecom_webhook_key
        self.api_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={self.webhook_key}"
        self.api_key = self.settings.openai_api_key
        self.api_base = self.settings.openai_api_base
        self.model = self.settings.openai_summary_model
        self._is_configured = bool(self.webhook_key)

    @property
    def is_available(self) -> bool:
        """检查是否配置"""
        return self._is_configured

    async def send(
            self,
            content: str,
            msg_type: str = "text",
            file_name: Optional[str] = None
    ) -> bool:
        """
        发送消息

        Args:
            content: 消息内容
            msg_type: 消息类型
            file_name: 文件名

        Returns:
            bool: 是否成功
        """
        if not self.is_available:
            logger.warning("企业微信 Webhook 未配置")
            return False

        try:
            # 检测是否需要特殊处理
            from app.services.notifier import content_converter
            if content_converter.check_length(content):
                logger.info("内容超过长度限制，尝试转为文件发送")
                return await self._send_as_file(content, file_name=file_name)

            # 若长度未超过限制，则正常发送
            payload = self._build_payload(msg_type, content)

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.api_url, json=payload)
                result = response.json()

                if result.get("errcode") == 0:
                    logger.info(f"企业微信消息发送成功")
                    return True
                else:
                    logger.error(f"企业微信发送失败: {result}")
                    return False

        except Exception as e:
            logger.error(f"企业微信发送异常: {e}")
            return False

    async def _send_as_file(
            self,
            content: str,
            file_name: Optional[str] = None,
    ) -> bool:
        """
        将内容作为文件发送（PDF优先，Markdown备选）

        发送优先级：
        1. PDF文件（使用WeasyPrint + mistune生成）
        2. Markdown文件（降级方案）
        3. 卡片摘要（最后降级方案）
        """
        from app.services.notifier import content_converter

        # ===== 方案1: 尝试发送PDF文件 =====
        pdf_result = await self._send_as_pdf(content, file_name=file_name)
        if pdf_result:
            logger.info("PDF文件发送成功")
            return True

        # # ===== 方案2: 降级为Markdown文件 =====
        logger.info("PDF生成/发送失败，尝试Markdown文件...")
        md_result = await self._send_as_markdown(content, file_name=file_name)
        if md_result:
            logger.info("Markdown文件发送成功")
            return True
        #
        # # ===== 方案3: 最后降级为卡片摘要 =====
        # logger.info("文件发送失败，尝试降级为卡片摘要...")
        # return await self._send_card_summary(content)

        return False

    async def _send_as_pdf(
            self,
            content: str,
            file_name: Optional[str] = None,
    ) -> bool:
        """将Markdown内容转换为PDF并发送"""
        from app.services.notifier import content_converter

        try:
            # 1. 生成PDF文件（使用WeasyPrint + mistune）
            logger.info("开始生成PDF文件...")
            pdf_bytes = await content_converter.markdown_to_pdf(content)

            if not pdf_bytes:
                logger.warning("PDF生成失败，返回空字节")
                return False

            # 2. 生成文件名
            filename = content_converter.generate_pdf_filename(file_name)

            # 3. 调用企业微信上传临时文件接口
            upload_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={self.webhook_key}&type=file"

            async with httpx.AsyncClient(timeout=60.0) as client:
                files = {
                    "file": (filename, pdf_bytes, "application/pdf")
                }
                response = await client.post(upload_url, files=files)
                result = response.json()

                if result.get("errcode") != 0:
                    logger.error(f"PDF文件上传失败: {result}")
                    return False

                # 4. 发送文件消息
                media_id = result.get("media_id")
                logger.info(f"PDF文件上传成功，media_id: {media_id}")
                return await self._send_file_message(media_id, filename)

        except ImportError as e:
            logger.warning(f"PDF依赖未安装，跳过PDF方案: {e}")
            return False
        except Exception as e:
            logger.error(f"PDF生成或发送失败: {e}")
            return False

    async def _send_as_markdown(
            self,
            content: str,
            file_name: Optional[str] = None,
    ) -> bool:
        """将Markdown内容保存为文件并发送"""
        from app.services.notifier import content_converter

        try:
            # 1. 将字符串编码为 bytes（直接在内存中处理）
            file_data = content.encode('utf-8')

            # 2. 生成文件名
            filename = content_converter.generate_filename(file_name)

            # 3. 调用企业微信上传临时文件接口
            upload_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={self.webhook_key}&type=file"

            async with httpx.AsyncClient(timeout=60.0) as client:
                files = {"file": (filename, file_data, "text/markdown")}
                response = await client.post(upload_url, files=files)
                result = response.json()

                if result.get("errcode") != 0:
                    logger.error(f"Markdown文件上传失败: {result}")
                    return False

                # 4. 发送文件消息
                media_id = result.get("media_id")
                return await self._send_file_message(media_id, filename)

        except Exception as e:
            logger.error(f"Markdown文件发送失败: {e}")
            return False

    async def _send_file_message(self, media_id: str, filename: str) -> bool:
        """发送文件消息（通用）"""
        try:
            payload = {
                "msgtype": "file",
                "file": {"media_id": media_id}
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.api_url, json=payload)
                result = response.json()

                if result.get("errcode") == 0:
                    logger.info(f"文件消息发送成功: {filename}")
                    return True
                else:
                    logger.error(f"文件消息发送失败: {result}")
                    return False
        except Exception as e:
            logger.error(f"发送文件消息异常: {e}")
            return False

    def _build_payload(self, msg_type: str, content: str) -> dict:
        """
        构建消息载荷

        Args:
            msg_type: 消息类型
            content: 内容

        Returns:
            dict: 消息载荷
        """
        if msg_type == "markdown":
            return {
                "msgtype": "markdown",
                "markdown": {
                    "content": content
                }
            }
        elif msg_type == "image":
            return {
                "msgtype": "image",
                "image": {
                    "base64": content  # 需要Base64编码
                }
            }
        else:
            # 默认文本
            return {
                "msgtype": "text",
                "text": {
                    "content": content
                }
            }

    async def send_article(
        self,
        title: str,
        summary: str,
        url: str,
        source: str,
        tags: Optional[str] = None,
        score: Optional[float] = None,
    ) -> bool:
        """
        发送文章

        Args:
            title: 标题
            summary: 摘要
            url: 链接
            source: 来源
            tags: 标签
            score: 评分

        Returns:
            bool: 是否成功
        """
        # 构建Markdown格式
        content = f"## 📰 {title}\n\n"

        if tags:
            content += f"**标签**：{tags}\n\n"

        if score is not None:
            content += f"**评分**: ⭐ {score}/10\n\n"

        content += f"{summary}\n\n"
        content += f"**来源**: {source}\n\n"
        content += f"🔗 [阅读原文]({url})"

        return await self.send(content, "markdown")