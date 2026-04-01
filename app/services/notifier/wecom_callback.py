# -*- coding: utf-8 -*-
"""
企业微信自建应用回调处理模块

使用企业微信官方 SDK 进行消息加解密
"""
import asyncio
import time
import uuid
from datetime import datetime
from typing import Optional

import httpx
import json
import logging
from fastapi import APIRouter, Request
from fastapi.responses import Response
from urllib.parse import unquote

from app.config import get_settings
from app.utils.WXBizMsgCrypt import WXBizMsgCrypt
from app.utils import ierror
from app.services.agentic.agent_manage import get_agent_manage, AgentManage
from app.services.processor.llm_manager import llm_manager, LLMMode
from app.services.agentic.context_manager import context_manager

logger = logging.getLogger(__name__)

router = APIRouter()
settings = get_settings()

# 创建企业微信加密解密实例
# sReceiveId: 企业微信corpid
wxcrypt = WXBizMsgCrypt(
    sToken=settings.wecom_token,
    sEncodingAESKey=settings.wecom_aes_key,
    sReceiveId=settings.wecom_corp_id
)


# 企业微信回调处理
@router.get("/webhook/wecom")
async def wecom_verify(request: Request):
    """
    企业微信URL验证（GET请求）
    
    用于验证回调URL的有效性
    """
    query = request.query_params
    
    # 企业微信要求对参数进行URL解码
    msg_signature = unquote(query.get("msg_signature", ""))
    timestamp = unquote(query.get("timestamp", ""))
    nonce = unquote(query.get("nonce", ""))
    echostr = unquote(query.get("echostr", ""))
    
    # 使用官方SDK验证URL
    ret, reply_echostr = wxcrypt.VerifyURL(msg_signature, timestamp, nonce, echostr)
    
    if ret != ierror.WXBizMsgCrypt_OK:
        print(f"企业微信URL验证失败: 错误码={ret}")
        return Response(content="", media_type="text/plain")
    
    # 验证成功，返回解密后的echostr
    return Response(content=reply_echostr, media_type="text/plain")


_user_data = {}

@router.post("/webhook/wecom")
async def wecom_callback(request: Request):
    """
    企业微信消息回调（POST请求）
    
    接收用户发送的消息，并回复
    """
    # 获取请求参数
    query = request.query_params
    msg_signature = query.get("msg_signature", "")
    timestamp = query.get("timestamp", "")
    nonce = query.get("nonce", "")
    
    # 获取请求体
    post_data = await request.body()
    post_data = post_data.decode("utf-8")
    
    # 使用官方SDK解密消息
    ret, xml_content = wxcrypt.DecryptMsg(post_data, msg_signature, timestamp, nonce)
    
    if ret != ierror.WXBizMsgCrypt_OK:
        logger.error(f"企业微信消息解密失败: 错误码={ret}")
        return Response(content="success", media_type="text/plain")
    
    # 解析XML获取消息内容
    import xml.etree.ElementTree as ET
    try:
        xml_tree = ET.fromstring(xml_content)
        content = xml_tree.find("Content").text or ""
        from_user = xml_tree.find("FromUserName").text or str(uuid.uuid4())
    except Exception as e:
        logger.error(f"解析消息XML失败: {e}")
        return Response(content="success", media_type="text/plain")
    
    # 获取用户发送的内容
    content = content.strip()

    # ===== 企业微信回调模式：回复消息必须通过主动发送API ===== #
    # 1. 先返回 "success" 表示接收成功（企业微信要求5秒内响应）
    # 2. 然后通过主动发送消息API回复用户

    # 使用agent处理消息
    global _user_data

    available_models = [
        model for model in llm_manager.models
        if model.is_available() and model.can_use_tool
    ]

    if not available_models:
        reply_text = "没有可用模型，服务暂时不可用，请稍后重试。"
        if reply_text:
            await wecom_send_message(from_user, reply_text)
        return Response(content="success", media_type="text/plain")

    # 获取或创建会话 ID
    session_id, exist = context_manager.get_session_id(from_user)

    if not exist or from_user not in _user_data:
        await set_new_agent(from_user)

    # 设置最大重试次数
    max_retries = len(available_models) if available_models else 1
    retry_count = 0

    while retry_count < max_retries:
        logger.info(f'当前调用的模型：{_user_data[from_user]["model"].model_name}')

        async with _user_data[from_user]['model']._semaphore:
            try:
                if _user_data[from_user]['model'].model_name not in llm_manager.llm_err_statistic:
                    llm_manager.llm_err_statistic[_user_data[from_user]['model'].model_name] = 0

                # 处理用户输入
                reply_text = await _user_data[from_user]['agent'].process(
                    user_input=content,
                    session_id=session_id
                )

                llm_manager.llm_err_statistic[
                    _user_data[from_user]['model'].model_name
                ] = 0

                if reply_text:
                    break

            except Exception as e:
                retry_count += 1
                # logger.error(f"agent调用出错：{e}")

                # 检查是否是可重试的错误
                error_str = str(e).lower()

                # 检查是否是数据库事务错误（不应重试，而是等待后重试）
                is_db_error = any(keyword in error_str for keyword in [
                    'transaction', 'sqlite', 'database', 'cannot commit',
                    'cannot start a transaction'
                ])

                is_llm_retryable = any(keyword in error_str for keyword in [
                    '429', 'too many requests', 'rate limit', 'timeout',
                    'connection', 'temporarily unavailable', 'service unavailable'
                ])

                if is_db_error:
                    # 数据库错误：等待后重试，不创建新实例
                    wait_time = 2 * retry_count
                    logger.warning(f"数据库事务错误，等待{wait_time}秒后重试: {e}")
                    await asyncio.sleep(wait_time)
                    # 不调用 set_new_agent，复用现有实例

                elif is_llm_retryable and retry_count < max_retries:
                    # 重新获取可用模型
                    await set_new_agent(from_user)
                    logger.warning(
                        f"LLM调用触发可重试错误 [{_user_data[from_user]['model'].provider.value}/{_user_data[from_user]['model'].model_name}], "
                        f"错误: {e}, 重试 (第{retry_count}/{max_retries}次)"
                    )
                elif retry_count >= max_retries:
                    logger.error(
                        f"LLM调用失败 [{_user_data[from_user]['model'].provider.value}/{_user_data[from_user]['model'].model_name}], "
                        f"已达到最大重试次数 {max_retries}: {e}"
                    )
                    reply_text = "已达到最大重试次数，服务暂时不可用，请稍后重试。"

                else:
                    logger.error(f"未知错误，处理消息失败：{e}")

                    # 统计大模型调用错误
                    llm_manager.llm_err_statistic[_user_data[from_user]['model'].model_name] += 1

                    if llm_manager.llm_err_statistic[_user_data[from_user]['model'].model_name] >= 5:
                        llm_manager.models = [
                            model for model in llm_manager.models
                            if model.model_name != _user_data[from_user]['model'].model_name
                        ]
                        logger.warning(
                            f"模型{_user_data[from_user]['model'].model_name}已经连续调用失败5次，已从模型注册列表中删除"
                        )
                        # available_models = [
                        #     model for model in available_models
                        #     if model.model_name != _user_data[from_user]['model'].model_name
                        # ]

                    await set_new_agent(from_user)




    # 更新会话上下文
    context_manager.update_session(
        session_id=session_id,
        user_input=content,
        assistant_response=reply_text
    )
    
    # 主动发送消息回复用户
    if reply_text:
        send_result = await wecom_send_message(from_user, reply_text)

    # 清除用户工具调用缓存
    if from_user in _user_data and 'agent' in _user_data[from_user]:
        agent_obj = _user_data[from_user]['agent']
        if hasattr(agent_obj, 'tool_cache_middleware'):
            agent_obj.tool_cache_middleware.clear_user_cache()

    # 返回 success 表示接收成功
    return Response(content="success", media_type="text/plain")


@router.post("/agent/test")
async def agent_test(request: Request):
    """
    用于测试agent功能（POST请求）

    接收用户发送的消息，并回复
    """

    # 获取请求体
    post_data = await request.body()
    content = json.loads(post_data.decode("utf-8")).get('content', None)
    from_user = json.loads(post_data.decode("utf-8")).get('user_id', str(uuid.uuid4()))
    logger.info(f'接收到的数据：{content}')

    available_models = [
        model for model in llm_manager.models
        if model.is_available() and model.can_use_tool
    ]
    if not content:
        return Response(content="请输入内容", media_type="text/plain")

    if not available_models:
        reply_text = "没有可用模型，服务暂时不可用，请稍后重试。"
        if reply_text:
            return Response(content=reply_text, media_type="text/plain")

    # 获取或创建会话 ID
    session_id, exist = context_manager.get_session_id(from_user)

    if not exist or from_user not in _user_data:
        await set_new_agent(from_user)

    # 设置最大重试次数
    max_retries = len(available_models) if available_models else 1
    retry_count = 0

    while retry_count < max_retries:
        logger.info(f'当前调用的模型：{_user_data[from_user]["model"].model_name}')

        async with _user_data[from_user]['model']._semaphore:
            try:
                if _user_data[from_user]['model'].model_name not in llm_manager.llm_err_statistic:
                    llm_manager.llm_err_statistic[_user_data[from_user]['model'].model_name] = 0

                # 处理用户输入
                reply_text = await _user_data[from_user]['agent'].process(
                    user_input=content,
                    session_id=session_id
                )

                llm_manager.llm_err_statistic[
                    _user_data[from_user]['model'].model_name
                ] = 0


                if reply_text:
                    logger.info(type(reply_text))
                    break

            except Exception as e:
                retry_count += 1
                # logger.error(f"agent调用出错：{e}")

                # 检查是否是可重试的错误
                error_str = str(e).lower()

                # 检查是否是数据库事务错误（不应重试，而是等待后重试）
                is_db_error = any(keyword in error_str for keyword in [
                    'transaction', 'sqlite', 'database', 'cannot commit',
                    'cannot start a transaction'
                ])

                is_llm_retryable = any(keyword in error_str for keyword in [
                    '429', 'too many requests', 'rate limit', 'timeout',
                    'connection', 'temporarily unavailable', 'service unavailable'
                ])

                if is_db_error:
                    # 数据库错误：等待后重试，不创建新实例
                    wait_time = 2 * retry_count
                    logger.warning(f"数据库事务错误，等待{wait_time}秒后重试: {e}")
                    await asyncio.sleep(wait_time)
                    # 不调用 set_new_agent，复用现有实例

                elif is_llm_retryable and retry_count < max_retries:
                    # 重新获取可用模型
                    await set_new_agent(from_user)
                    logger.warning(
                        f"LLM调用触发可重试错误 [{_user_data[from_user]['model'].provider.value}/{_user_data[from_user]['model'].model_name}], "
                        f"错误: {e}, 重试 (第{retry_count}/{max_retries}次)"
                    )
                elif retry_count >= max_retries:
                    logger.error(
                        f"LLM调用失败 [{_user_data[from_user]['model'].provider.value}/{_user_data[from_user]['model'].model_name}], "
                        f"已达到最大重试次数 {max_retries}: {e}"
                    )
                    reply_text = "已达到最大重试次数，服务暂时不可用，请稍后重试。"

                else:
                    logger.error(f"未知错误，处理消息失败：{e}")

                    # 统计大模型调用错误
                    llm_manager.llm_err_statistic[_user_data[from_user]['model'].model_name] += 1

                    if llm_manager.llm_err_statistic[_user_data[from_user]['model'].model_name] >= 5:
                        llm_manager.models = [
                            model for model in llm_manager.models
                            if model.model_name != _user_data[from_user]['model'].model_name
                        ]
                        logger.warning(
                            f"模型{_user_data[from_user]['model'].model_name}已经连续调用失败5次，已从模型注册列表中删除"
                        )
                        # available_models = [
                        #     model for model in available_models
                        #     if model.model_name != _user_data[from_user]['model'].model_name
                        # ]

                    await set_new_agent(from_user)

    # 更新会话上下文
    context_manager.update_session(
        session_id=session_id,
        user_input=content,
        assistant_response=reply_text
    )

    # 清除用户工具调用缓存
    if from_user in _user_data and 'agent' in _user_data[from_user]:
        agent_obj = _user_data[from_user]['agent']
        if hasattr(agent_obj, 'tool_cache_middleware'):
            agent_obj.tool_cache_middleware.clear_user_cache()

    if reply_text:
        res_text = json.dumps({
            "content": reply_text,
            "user_id": from_user,
        })
        return Response(content=res_text, media_type="text/plain")


async def set_new_agent(
        from_user
):

    global _user_data

    # 确保用户字典存在
    if from_user not in _user_data:
        _user_data[from_user] = {}

    _selected_model = llm_manager.to_select_model(
        use_tool=True,
        llm_mode=LLMMode.USE_TOOL_REQUIRED,
    )
    # 如果没有可用的模型就直接返回用户服务不可用
    # if not _selected_model:
    #     reply_text = "没有可用模型，服务暂时不可用，请稍后重试。"
    #
    #     await wecom_send_message(from_user, reply_text)
    #     return Response(content="success", media_type="text/plain")

    _user_data[from_user]['agent'] = get_agent_manage(
        _selected_model=_selected_model,
        store_type='sqlite',
    )
    _user_data[from_user]['model'] = _selected_model


def cleanup_expired_agents() -> int:
    """清理过期的Agent实例

    清理条件：
    - 用户在 context_manager 中没有有效会话
    - 或用户会话已过期

    Returns:
        清理的Agent数量
    """
    if not _user_data:
        return 0

    expired_users = []

    for user_id in list(_user_data.keys()):
        # 检查用户在 context_manager 中是否有有效会话
        if user_id in context_manager._user_sessions:
            sess_id = context_manager._user_sessions[user_id]
            if sess_id in context_manager._session_metadata:
                created_time = context_manager._session_metadata[sess_id]["created_at"]
                if datetime.now() - created_time < context_manager._ttl:
                    # 会话有效，跳过
                    continue

        # 会话过期或不存在，清理Agent
        expired_users.append(user_id)

    for user_id in expired_users:
        # # 显式关闭Agent资源
        # if 'agent' in _user_data[user_id]:
        #     agent_obj = _user_data[user_id]['agent']
        #     if hasattr(agent_obj, 'close'):
        #         try:
        #             agent_obj.close()
        #         except Exception as e:
        #             logger.error(f"关闭Agent失败 [{user_id}]: {e}")

        del _user_data[user_id]
        logger.info(f"清理过期Agent: {user_id}")

    return len(expired_users)


TOKEN_EXPIRES_SECONDS = 7200 - 300

def _get_cached_access_token(user_id: str = None) -> Optional[str]:
    """
    获取缓存的 access_token

    Returns:
        token字符串，如果不存在或已过期返回None
    """
    if not user_id or user_id not in _user_data:
        return None

    user_data = _user_data[user_id]

    # 检查是否有缓存的 token
    if (
            "token_data" not in user_data
            or "access_token" not in user_data["token_data"]
            or "token_expires_at" not in user_data["token_data"]
    ):
        return None


    # 检查是否过期
    expires_at = user_data["token_data"]["token_expires_at"]
    if time.time() >= expires_at:
        # token 已过期
        return None

    return user_data["token_data"]["access_token"]


def _save_access_token(user_id: str, access_token: str):
    """
    保存 access_token 到缓存

    Args:
        user_id: 用户ID
        access_token: token字符串
    """
    if user_id not in _user_data:
        _user_data[user_id] = {}

    if "token_data" not in _user_data[user_id]:
        _user_data[user_id]["token_data"] = {}

    # 记录当前时间和过期时间
    current_time = time.time()

    _user_data[user_id]["token_data"]["access_token"] = access_token
    _user_data[user_id]["token_data"]["token_expires_at"] = current_time + TOKEN_EXPIRES_SECONDS

    logger.info(f"已缓存 access_token，用户: {user_id}，过期时间: {TOKEN_EXPIRES_SECONDS}秒")


async def _get_or_refresh_access_token(user_id: str = None) -> Optional[str]:
    """
    获取 access_token（优先使用缓存，必要时刷新）

    Args:
        user_id: 用户ID（可选，用于分用户缓存）

    Returns:
        access_token 字符串
    """
    # 1. 尝试从缓存获取
    cached_token = _get_cached_access_token(user_id)
    if cached_token:
        logger.debug(f"使用缓存的 access_token")
        return cached_token

    # 2. 缓存不存在或已过期，重新获取
    try:
        token_url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        token_params = {
            "corpid": settings.wecom_corp_id,
            "corpsecret": settings.wecom_agent_secret
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(token_url, params=token_params)
            data = response.json()

            if data.get("errcode") != 0:
                logger.error(f"获取 access_token 失败: {data}")
                return None

            access_token = data.get("access_token")

            # 3. 保存到缓存
            _save_access_token(user_id or "global", access_token)

            return access_token

    except Exception as e:
        logger.error(f"获取 access_token 异常: {e}")
        return None


# 企业微信主动发送消息（可选功能）
async def wecom_send_message(user_id: str, content: str) -> bool:
    """
    主动发送消息给用户
    
    Args:
        user_id: 用户ID
        content: 消息内容
    
    Returns:
        bool: 是否发送成功
    """
    if not settings.wecom_corp_id or not settings.wecom_agent_id:
        logger.warning('未配置公司ID或应用ID')
        return False
    
    try:
        # 1. 获取 access_token（优先缓存）
        access_token = await _get_or_refresh_access_token(user_id)

        if not access_token:
            logger.error("无法获取 access_token")
            return False
            
        # 发送消息
        send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send"
        send_params = {"access_token": access_token}
            
        send_data = {
            "touser": user_id,
            "msgtype": "markdown",
            "agentid": settings.wecom_agent_id,
            "markdown": {
                "content": content
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:

            send_response = await client.post(
                send_url,
                params=send_params,
                json=send_data,
            )
            result = send_response.json()

            if result.get("errcode") != 0:
                logger.error(f"企业微信消息发送失败: errcode={result.get('errcode')}, errmsg={result.get('errmsg')}")
                return False
            return result.get("errcode") == 0
            
    except Exception as e:
        print(f"发送企业微信消息失败: {e}")
        return False
