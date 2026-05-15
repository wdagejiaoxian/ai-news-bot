# -*- coding: utf-8 -*-
"""
企业微信 Webhook 动态通知器

基于数据库 WebhookConfig 动态创建，每次推送使用对应 webhook 的密钥
"""

from typing import Optional, List

import httpx

from app.config import get_settings
from app.services.notifier.base import BaseDynamicNotifier, register_notifier

logger = __import__('logging').getLogger(__name__)


@register_notifier("wecom")
class DynamicWeComNotifier(BaseDynamicNotifier):
    """
    动态企业微信 Webhook Notifier

    基于 WebhookConfig 动态创建，每次推送使用对应 webhook 的密钥
    继承 BaseDynamicNotifier，使用其公共逻辑
    """

    def _init_notifier(self) -> None:
        """企业微信特定初始化"""
        settings = get_settings()
        self.webhook_key = self._raw_key
        self.api_url = f"{settings.wecom_api_base_url}/cgi-bin/webhook/send?key={self.webhook_key}"

    async def send(
            self,
            content: str,
            msg_type: str = "text",
            **kwargs
    ) -> bool:
        """发送消息"""
        # 获取 file_name 参数（如果提供）
        file_name = kwargs.get('file_name')
        if not self.is_available:
            logger.warning(f"企业微信 Webhook 未配置: {self.webhook_config.name}")
            return False

        from app.services.notifier import content_converter

        try:
            if content_converter.check_length(content):
                logger.info("内容超过长度限制，尝试转为文件发送")
                return await self._send_as_file(content, file_name=file_name)

            payload = self._build_payload(msg_type, content)
            settings = get_settings()

            async with httpx.AsyncClient(timeout=settings.wecom_webhook_timeout) as client:
                response = await client.post(self.api_url, json=payload)
                result = response.json()

                if result.get("errcode") == 0:
                    logger.info(f"企业微信消息发送成功: {self.webhook_config.name}")
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
        """将内容作为文件发送"""
        pdf_result = await self._send_as_pdf(content, file_name=file_name)
        if pdf_result:
            logger.info("PDF文件发送成功")
            return True

        logger.info("PDF生成/发送失败，尝试Markdown文件...")
        md_result = await self._send_as_markdown(content, file_name=file_name)
        if md_result:
            logger.info("Markdown文件发送成功")
            return True

        return False

    async def _send_as_pdf(
            self,
            content: str,
            file_name: Optional[str] = None,
    ) -> bool:
        """将Markdown内容转换为PDF并发送"""
        from app.services.notifier import content_converter
        settings = get_settings()

        try:
            pdf_bytes = await content_converter.markdown_to_pdf(content)
            if not pdf_bytes:
                logger.warning("PDF生成失败，返回空字节")
                return False

            filename = content_converter.generate_pdf_filename(file_name)
            upload_url = f"{settings.wecom_api_base_url}/cgi-bin/webhook/upload_media?key={self.webhook_key}&type=file"

            async with httpx.AsyncClient(timeout=settings.wecom_upload_timeout) as client:
                files = {"file": (filename, pdf_bytes, "application/pdf")}
                response = await client.post(upload_url, files=files)
                result = response.json()

                if result.get("errcode") != 0:
                    logger.error(f"PDF文件上传失败: {result}")
                    return False

                media_id = result.get("media_id")
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
        settings = get_settings()

        try:
            file_data = content.encode('utf-8')
            filename = content_converter.generate_filename(file_name)
            upload_url = f"{settings.wecom_api_base_url}/cgi-bin/webhook/upload_media?key={self.webhook_key}&type=file"

            async with httpx.AsyncClient(timeout=settings.wecom_upload_timeout) as client:
                files = {"file": (filename, file_data, "text/markdown")}
                response = await client.post(upload_url, files=files)
                result = response.json()

                if result.get("errcode") != 0:
                    logger.error(f"Markdown文件上传失败: {result}")
                    return False

                media_id = result.get("media_id")
                return await self._send_file_message(media_id, filename)

        except Exception as e:
            logger.error(f"Markdown文件发送失败: {e}")
            return False

    async def _send_file_message(self, media_id: str, filename: str) -> bool:
        """发送文件消息"""
        settings = get_settings()
        try:
            payload = {"msgtype": "file", "file": {"media_id": media_id}}

            async with httpx.AsyncClient(timeout=settings.wecom_api_timeout) as client:
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
        """构建消息载荷"""
        if msg_type == "markdown":
            return {"msgtype": "markdown", "markdown": {"content": content}}
        elif msg_type == "image":
            return {"msgtype": "image", "image": {"base64": content}}  # 需要Base64编码
        else:
            return {"msgtype": "text", "text": {"content": content}}

    async def batch_send_article(self, article_list: List) -> bool:
        """
        批量发送文章

        重写父类的批量推送逻辑，直接构建一个包含所有文章的Markdown内容进行发送，避免多次调用API
        """
        # 构建Markdown格式
        content = ''
        for i, article in enumerate(article_list):
            content += f"## 📰 {i + 1}. {article.title}\n\n"

            if article.tags:
                content += f"**标签**：{article.tags}\n\n"

            if article.score is not None:
                content += f"**评分**: ⭐ {article.score}/100\n\n"

            content += f"**摘要**: {article.summary}\n\n"
            content += f"**来源**: {article.source_name}\n\n"
            content += f"🔗 [阅读原文]({article.url})\n\n"

        return await self.send(content, "markdown", file_name='高分资讯')