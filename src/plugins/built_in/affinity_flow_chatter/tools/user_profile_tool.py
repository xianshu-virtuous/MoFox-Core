"""
用户画像更新工具

采用两阶段设计：
1. 工具调用模型(tool_use)负责判断是否需要更新，传入基本信息
2. 关系追踪模型(relationship_tracker)负责生成高质量的、有人设特色的印象内容
"""

import time
from typing import Any

from sqlalchemy import select

from src.common.database.compatibility import get_db_session
from src.common.database.core.models import UserRelationships
from src.common.logger import get_logger
from src.config.config import global_config, model_config
from src.plugin_system import BaseTool, ToolParamType

logger = get_logger("user_profile_tool")


class UserProfileTool(BaseTool):
    """用户画像更新工具

    两阶段设计：
    - 第一阶段：tool_use模型判断是否更新，传入简要信息
    - 第二阶段：relationship_tracker模型生成有人设特色的印象描述
    """

    name = "update_user_profile"
    description = """当你通过聊天对某个人产生了新的认识或印象时使用此工具。
调用时机：当你发现TA透露了新信息、展现了性格特点、表达了兴趣爱好，或你们的互动让你对TA有了新感受时。
注意：impression_hint只需要简单描述你观察到的要点，系统会自动用你的人设风格来润色生成最终印象。"""
    parameters = [
        ("target_user_id", ToolParamType.STRING, "目标用户的ID（必须）", True, None),
        ("target_user_name", ToolParamType.STRING, "目标用户的名字/昵称（必须，用于生成印象时称呼）", True, None),
        ("user_aliases", ToolParamType.STRING, "TA的其他昵称或别名，多个用逗号分隔（可选）", False, None),
        ("impression_hint", ToolParamType.STRING, "【简要描述】你观察到的关于TA的要点，如'很健谈，喜欢聊游戏，有点害羞'。系统会用你的人设风格润色（可选）", False, None),
        ("preference_keywords", ToolParamType.STRING, "TA的兴趣爱好关键词，如'编程,游戏,音乐'，用逗号分隔（可选）", False, None),
        ("affection_score", ToolParamType.FLOAT, "你对TA的好感度(0.0-1.0)。0.3=普通认识，0.5=还不错的朋友，0.7=很喜欢，0.9=非常亲密。打分要保守（可选）", False, None),
    ]
    available_for_llm = True
    history_ttl = 5

    async def execute(self, function_args: dict[str, Any]) -> dict[str, Any]:
        """执行用户画像更新

        Args:
            function_args: 工具参数

        Returns:
            dict: 执行结果
        """
        try:
            # 提取参数
            target_user_id = function_args.get("target_user_id")
            target_user_name = function_args.get("target_user_name", target_user_id)
            if not target_user_id:
                return {
                    "type": "error",
                    "id": "user_profile_update",
                    "content": "错误：必须提供目标用户ID"
                }

            # 从LLM传入的参数
            new_aliases = function_args.get("user_aliases", "")
            impression_hint = function_args.get("impression_hint", "")
            new_keywords = function_args.get("preference_keywords", "")
            new_score = function_args.get("affection_score")

            # 从数据库获取现有用户画像
            existing_profile = await self._get_user_profile(target_user_id)

            # 如果LLM没有传入任何有效参数，返回提示
            if not any([new_aliases, impression_hint, new_keywords, new_score is not None]):
                return {
                    "type": "info",
                    "id": target_user_id,
                    "content": "提示：需要提供至少一项更新内容（别名、印象描述、偏好关键词或好感分数）"
                }

            # 🎯 核心：使用relationship_tracker模型生成高质量印象
            final_impression = existing_profile.get("relationship_text", "")
            if impression_hint:
                final_impression = await self._generate_impression_with_personality(
                    target_user_name=str(target_user_name) if target_user_name else str(target_user_id),
                    impression_hint=str(impression_hint),
                    existing_impression=str(existing_profile.get("relationship_text", "")),
                    preference_keywords=str(new_keywords or existing_profile.get("preference_keywords", "")),
                )

            # 构建最终画像
            final_profile = {
                "user_aliases": new_aliases if new_aliases else existing_profile.get("user_aliases", ""),
                "relationship_text": final_impression,
                "preference_keywords": new_keywords if new_keywords else existing_profile.get("preference_keywords", ""),
                "relationship_score": new_score if new_score is not None else existing_profile.get("relationship_score", global_config.affinity_flow.base_relationship_score),
            }

            # 确保分数在有效范围内
            final_profile["relationship_score"] = max(0.0, min(1.0, float(final_profile["relationship_score"])))

            # 更新数据库
            await self._update_user_profile_in_db(target_user_id, final_profile)

            # 构建返回信息
            updates = []
            if final_profile.get("user_aliases"):
                updates.append(f"别名: {final_profile['user_aliases']}")
            if final_profile.get("relationship_text"):
                updates.append(f"印象: {final_profile['relationship_text'][:80]}...")
            if final_profile.get("preference_keywords"):
                updates.append(f"偏好: {final_profile['preference_keywords']}")
            if final_profile.get("relationship_score") is not None:
                updates.append(f"好感分: {final_profile['relationship_score']:.2f}")

            result_text = f"已更新用户 {target_user_name} 的画像：\n" + "\n".join(updates)
            logger.info(f"用户画像更新成功: {target_user_id}")

            return {
                "type": "user_profile_update",
                "id": target_user_id,
                "content": result_text
            }

        except Exception as e:
            logger.error(f"用户画像更新失败: {e}")
            return {
                "type": "error",
                "id": function_args.get("target_user_id", "unknown"),
                "content": f"用户画像更新失败: {e!s}"
            }

    async def _generate_impression_with_personality(
        self,
        target_user_name: str,
        impression_hint: str,
        existing_impression: str,
        preference_keywords: str,
    ) -> str:
        """使用relationship_tracker模型生成有人设特色的印象描述
        
        Args:
            target_user_name: 目标用户的名字
            impression_hint: 工具调用模型传入的简要观察
            existing_impression: 现有的印象描述
            preference_keywords: 用户的兴趣偏好
            
        Returns:
            str: 生成的印象描述
        """
        try:
            from src.llm_models.utils_model import LLMRequest
            
            # 获取人设信息
            bot_name = global_config.bot.nickname
            personality_core = global_config.personality.personality_core
            personality_side = global_config.personality.personality_side
            
            # 构建提示词
            prompt = f"""你是{bot_name}，现在要记录你对一个人的印象。

## 你的人设
{personality_core}

## 你的性格特点
{personality_side}

## 任务
根据下面的观察要点，用你自己的语气和视角，写一段对"{target_user_name}"的印象描述。

## 观察到的要点
{impression_hint}

## TA的兴趣爱好
{preference_keywords if preference_keywords else "暂未了解"}

## 之前对TA的印象（如果有）
{existing_impression if existing_impression else "这是第一次记录对TA的印象"}

## 写作要求
1. 用第一人称"我"来写，就像在写日记或者跟朋友聊天时描述一个人
2. 用"{target_user_name}"或"TA"来称呼对方，不要用"该用户"、"此人"
3. 写出你真实的、主观的感受，可以带情绪和直觉判断
4. 如果有之前的印象，可以结合新观察进行补充或修正
5. 长度控制在50-150字，自然流畅

请直接输出印象描述，不要加任何前缀或解释："""

            # 使用relationship_tracker模型
            llm = LLMRequest(
                model_set=model_config.model_task_config.relationship_tracker,
                request_type="user_profile.impression_generator"
            )
            
            response, _ = await llm.generate_response_async(
                prompt=prompt,
                temperature=0.7,
                max_tokens=300,
            )
            
            # 清理响应
            impression = response.strip()
            
            # 如果响应为空或太短，回退到原始hint
            if not impression or len(impression) < 10:
                logger.warning(f"印象生成结果过短，使用原始hint: {impression_hint}")
                return impression_hint
                
            logger.info(f"成功生成有人设特色的印象描述，长度: {len(impression)}")
            return impression
            
        except Exception as e:
            logger.error(f"生成印象描述失败，回退到原始hint: {e}")
            # 失败时回退到工具调用模型传入的hint
            return impression_hint

    async def _get_user_profile(self, user_id: str) -> dict[str, Any]:
        """从数据库获取用户现有画像

        Args:
            user_id: 用户ID

        Returns:
            dict: 用户画像数据
        """
        try:
            async with get_db_session() as session:
                stmt = select(UserRelationships).where(UserRelationships.user_id == user_id)
                result = await session.execute(stmt)
                profile = result.scalar_one_or_none()

                if profile:
                    return {
                        "user_name": profile.user_name or user_id,
                        "user_aliases": profile.user_aliases or "",
                        "relationship_text": profile.relationship_text or "",
                        "preference_keywords": profile.preference_keywords or "",
                        "relationship_score": float(profile.relationship_score) if profile.relationship_score is not None else global_config.affinity_flow.base_relationship_score,
                    }
                else:
                    # 用户不存在，返回默认值
                    return {
                        "user_name": user_id,
                        "user_aliases": "",
                        "relationship_text": "",
                        "preference_keywords": "",
                        "relationship_score": global_config.affinity_flow.base_relationship_score,
                    }
        except Exception as e:
            logger.error(f"获取用户画像失败: {e}")
            return {
                "user_name": user_id,
                "user_aliases": "",
                "relationship_text": "",
                "preference_keywords": "",
                "relationship_score": global_config.affinity_flow.base_relationship_score,
            }



    async def _update_user_profile_in_db(self, user_id: str, profile: dict[str, Any]):
        """更新数据库中的用户画像

        Args:
            user_id: 用户ID
            profile: 画像数据
        """
        try:
            current_time = time.time()

            async with get_db_session() as session:
                stmt = select(UserRelationships).where(UserRelationships.user_id == user_id)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    # 更新现有记录
                    existing.user_aliases = profile.get("user_aliases", "")
                    existing.relationship_text = profile.get("relationship_text", "")
                    existing.preference_keywords = profile.get("preference_keywords", "")
                    existing.relationship_score = profile.get("relationship_score", global_config.affinity_flow.base_relationship_score)
                    existing.last_updated = current_time
                else:
                    # 创建新记录
                    new_profile = UserRelationships(
                        user_id=user_id,
                        user_name=user_id,
                        user_aliases=profile.get("user_aliases", ""),
                        relationship_text=profile.get("relationship_text", ""),
                        preference_keywords=profile.get("preference_keywords", ""),
                        relationship_score=profile.get("relationship_score", global_config.affinity_flow.base_relationship_score),
                        last_updated=current_time
                    )
                    session.add(new_profile)

                await session.commit()
                logger.info(f"用户画像已更新到数据库: {user_id}")

        except Exception as e:
            logger.error(f"更新用户画像到数据库失败: {e}")
            raise


