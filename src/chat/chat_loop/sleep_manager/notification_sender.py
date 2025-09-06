import asyncio
import random
import hashlib
from src.common.logger import get_logger
from src.config.config import global_config
from src.plugin_system.apis import send_api, generator_api

logger = get_logger("notification_sender")


class NotificationSender:
    @staticmethod
    async def send_pre_sleep_notification():
        """异步生成并发送睡前通知"""
        try:
            groups = global_config.sleep_system.pre_sleep_notification_groups
            prompt = global_config.sleep_system.pre_sleep_prompt

            if not groups:
                logger.info("未配置睡前通知的群组，跳过发送。")
                return

            if not prompt:
                logger.warning("睡前通知的prompt为空，跳过发送。")
                return

            # 为防止消息风暴，稍微延迟一下
            await asyncio.sleep(random.uniform(5, 15))

            for group_id_str in groups:
                try:
                    # 格式 "platform:group_id"
                    parts = group_id_str.split(":")
                    if len(parts) != 2:
                        logger.warning(f"无效的群组ID格式: {group_id_str}")
                        continue

                    platform, group_id = parts

                    # 使用与 ChatStream.get_stream_id 相同的逻辑生成 stream_id
                    key = "_".join([platform, group_id])
                    stream_id = hashlib.md5(key.encode()).hexdigest()

                    logger.info(f"正在为群组 {group_id_str} (Stream ID: {stream_id}) 生成睡前消息...")

                    # 调用 generator_api 生成回复
                    success, reply_set, _ = await generator_api.generate_reply(
                        chat_id=stream_id, extra_info=prompt, request_type="schedule.pre_sleep_notification"
                    )

                    if success and reply_set:
                        # 提取文本内容并发送
                        reply_text = "".join([content for msg_type, content in reply_set if msg_type == "text"])
                        if reply_text:
                            logger.info(f"向群组 {group_id_str} 发送睡前消息: {reply_text}")
                            await send_api.text_to_stream(text=reply_text, stream_id=stream_id)
                        else:
                            logger.warning(f"为群组 {group_id_str} 生成的回复内容为空。")
                    else:
                        logger.error(f"为群组 {group_id_str} 生成睡前消息失败。")

                    await asyncio.sleep(random.uniform(2, 5))  # 避免发送过快

                except Exception as e:
                    logger.error(f"向群组 {group_id_str} 发送睡前消息失败: {e}")

        except Exception as e:
            logger.error(f"发送睡前通知任务失败: {e}")