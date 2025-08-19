# -*- coding: utf-8 -*-
"""
混合瞬时记忆系统 V2
融合LLM和向量两种记忆策略，智能选择最优方式
现已集成VectorInstantMemoryV2，支持：
- 自动定时清理过期记忆
- 相似度搜索
- 时间感知的记忆检索
- 更完善的错误处理
"""

import time
import asyncio
from typing import List, Optional, Dict, Any, Tuple, Union
from enum import Enum
from dataclasses import dataclass

from src.common.logger import get_logger
from .instant_memory import InstantMemory, MemoryItem
from .vector_instant_memory import VectorInstantMemoryV2

logger = get_logger(__name__)


class MemoryMode(Enum):
    """记忆处理模式"""
    VECTOR_ONLY = "vector_only"      # 仅使用向量系统
    LLM_ONLY = "llm_only"           # 仅使用LLM系统  
    LLM_PREFERRED = "llm_preferred"  # 优先LLM，向量备份
    HYBRID = "hybrid"               # 混合模式，并行处理


@dataclass
class StrategyDecision:
    """策略决策结果"""
    mode: MemoryMode
    confidence: float
    reason: str


class MemoryStrategy:
    """记忆策略判断器"""
    
    def __init__(self):
        # 情感关键词
        self.emotional_keywords = {
            "开心", "高兴", "兴奋", "激动", "快乐", "愉快", "满意",
            "伤心", "难过", "沮丧", "失落", "郁闷", "痛苦", "心疼",
            "生气", "愤怒", "气愤", "恼火", "烦躁", "讨厌", "厌烦", 
            "担心", "焦虑", "紧张", "害怕", "恐惧", "不安", "忧虑",
            "感动", "温馨", "幸福", "甜蜜", "浪漫", "美好", "珍惜",
            "重要", "关键", "关心", "在意", "喜欢", "爱", "想念"
        }
        
        # 重要信息标识词
        self.important_keywords = {
            "计划", "目标", "梦想", "理想", "希望", "打算", "准备",
            "决定", "选择", "考虑", "想要", "需要", "必须", "应该",
            "工作", "学习", "考试", "面试", "项目", "任务", "职业",
            "家人", "朋友", "恋人", "同事", "老师", "同学", "领导",
            "生日", "节日", "纪念日", "约会", "聚会", "旅行", "出差"
        }
        
    def analyze_content_complexity(self, text: str) -> Dict[str, Any]:
        """分析内容复杂度"""
        # 基础指标
        char_count = len(text)
        sentence_count = text.count('。') + text.count('!') + text.count('?') + 1
        
        # 情感词汇检测
        emotional_score = sum(1 for word in self.emotional_keywords if word in text)
        
        # 重要信息检测  
        importance_score = sum(1 for word in self.important_keywords if word in text)
        
        # 问号密度（询问程度）
        question_density = text.count('?') / max(char_count / 50, 1)
        
        # 语气词检测（口语化程度）
        casual_markers = ['啊', '呀', '嗯', '哦', '哈哈', '呵呵', '嘿嘿']
        casual_score = sum(1 for marker in casual_markers if marker in text)
        
        return {
            'char_count': char_count,
            'sentence_count': sentence_count,
            'emotional_score': emotional_score,
            'importance_score': importance_score,
            'question_density': question_density,
            'casual_score': casual_score
        }
    
    def decide_strategy(self, text: str) -> StrategyDecision:
        """智能决策使用哪种记忆策略"""
        if not text.strip():
            return StrategyDecision(MemoryMode.VECTOR_ONLY, 0.0, "空内容")
        
        analysis = self.analyze_content_complexity(text)
        # 决策逻辑
        
        # 1. 极短内容 -> 向量优先
        if analysis['char_count'] < 20:
            return StrategyDecision(
                MemoryMode.VECTOR_ONLY, 
                0.9, 
                f"内容过短({analysis['char_count']}字符)"
            )
        
        # 2. 高情感内容 -> LLM优先
        if analysis['emotional_score'] >= 2:
            return StrategyDecision(
                MemoryMode.LLM_PREFERRED,
                0.8 + min(analysis['emotional_score'] * 0.1, 0.2),
                f"检测到{analysis['emotional_score']}个情感词汇"
            )
        
        # 3. 重要信息 -> LLM优先
        if analysis['importance_score'] >= 3:
            return StrategyDecision(
                MemoryMode.LLM_PREFERRED,
                0.7 + min(analysis['importance_score'] * 0.05, 0.3),
                f"检测到{analysis['importance_score']}个重要信息标识"
            )
        
        # 4. 复杂长文本 -> 混合模式
        if analysis['char_count'] > 100 and analysis['sentence_count'] >= 3:
            return StrategyDecision(
                MemoryMode.HYBRID,
                0.75,
                f"复杂内容({analysis['char_count']}字符，{analysis['sentence_count']}句)"
            )
        
        # 5. 高询问度 -> LLM处理更准确
        if analysis['question_density'] > 0.3:
            return StrategyDecision(
                MemoryMode.LLM_PREFERRED,
                0.65,
                f"高询问密度({analysis['question_density']:.2f})"
            )
        
        # 6. 日常闲聊 -> 向量优先（快速）
        if analysis['casual_score'] >= 2 and analysis['char_count'] < 80:
            return StrategyDecision(
                MemoryMode.VECTOR_ONLY,
                0.7,
                f"日常闲聊内容(休闲标记:{analysis['casual_score']})"
            )
        
        # 7. 默认混合模式
        return StrategyDecision(
            MemoryMode.HYBRID,
            0.6,
            "中等复杂度内容，使用混合策略"
        )


class MemorySync:
    """记忆同步器 - 处理两套系统间的数据同步"""
    
    def __init__(self, llm_memory: InstantMemory, vector_memory: VectorInstantMemoryV2):
        self.llm_memory = llm_memory
        self.vector_memory = vector_memory
    
    async def sync_llm_to_vector(self, memory_item: MemoryItem):
        """将LLM生成的高质量记忆同步到向量系统"""
        try:
            # 使用新的V2系统的存储方法
            await self.vector_memory.store_message(
                content=memory_item.memory_text,
                sender="llm_memory"
            )
            logger.debug(f"LLM记忆已同步到向量系统: {memory_item.memory_text[:50]}...")
        except Exception as e:
            logger.error(f"LLM记忆同步到向量系统失败: {e}")
    
    async def sync_vector_to_llm(self, content: str, importance: float):
        """将向量系统的记忆同步到LLM系统（异步，低优先级）"""
        try:
            # 只有高重要性的向量记忆才值得同步到LLM系统
            if importance < 0.7:
                return
                
            # 创建MemoryItem
            memory_id = f"{self.llm_memory.chat_id}_{int(time.time() * 1000)}_vec_sync"
            
            # 简化的关键词提取（避免LLM调用）
            keywords = self._extract_simple_keywords(content)
            
            memory_item = MemoryItem(
                memory_id=memory_id,
                chat_id=self.llm_memory.chat_id,
                memory_text=content,
                keywords=keywords
            )
            
            await self.llm_memory.store_memory(memory_item)
            logger.debug(f"向量记忆已同步到LLM系统: {content[:50]}...")
            
        except Exception as e:
            logger.error(f"向量记忆同步到LLM系统失败: {e}")
    
    def _extract_simple_keywords(self, content: str) -> List[str]:
        """简单关键词提取（不使用LLM）"""
        # 基于常见词汇的简单提取
        import re
        
        # 移除标点符号，分词
        clean_text = re.sub(r'[，。！？；：""''（）【】\s]', ' ', content)
        words = [w.strip() for w in clean_text.split() if len(w.strip()) >= 2]
        
        # 简单去重和筛选
        keywords = list(set(words))[:10]  # 最多10个关键词
        return keywords


class HybridRetriever:
    """融合检索器 - 合并两种检索策略的结果"""
    
    def __init__(self, llm_memory: InstantMemory, vector_memory: VectorInstantMemoryV2):
        self.llm_memory = llm_memory
        self.vector_memory = vector_memory
    
    async def retrieve_memories(self, target: str, strategy: MemoryMode) -> Optional[Union[str, List[str]]]:
        """根据策略检索记忆"""
        
        if strategy == MemoryMode.VECTOR_ONLY:
            # 使用V2系统的获取相关记忆上下文方法
            context = await self.vector_memory.get_memory_for_context(target)
            return context if context else None
            
        elif strategy == MemoryMode.LLM_ONLY:
            return await self.llm_memory.get_memory(target)
            
        elif strategy == MemoryMode.LLM_PREFERRED:
            # 优先LLM，失败则降级到向量
            llm_result = await self.llm_memory.get_memory(target)
            if llm_result:
                return llm_result
            context = await self.vector_memory.get_memory_for_context(target)
            return context if context else None
            
        elif strategy == MemoryMode.HYBRID:
            # 并行查询两个系统
            return await self._hybrid_retrieve(target)
        
        return None
    
    async def _hybrid_retrieve(self, target: str) -> Optional[List[str]]:
        """混合检索 - 并行查询并融合结果"""
        try:
            # 并行查询
            results = await asyncio.gather(
                self.llm_memory.get_memory(target),
                self.vector_memory.get_memory_for_context(target),
                return_exceptions=True
            )
            
            llm_result, vector_result = results
            
            # 收集有效结果
            combined_memories = set()
            
            # 处理LLM结果
            if isinstance(llm_result, list) and llm_result:
                combined_memories.update(llm_result)
            elif isinstance(llm_result, str) and llm_result:
                combined_memories.add(llm_result)
            elif isinstance(llm_result, Exception):
                logger.warning(f"LLM检索出错: {llm_result}")
            
            # 处理向量结果
            if isinstance(vector_result, str) and vector_result:
                combined_memories.add(vector_result)
            elif isinstance(vector_result, Exception):
                logger.warning(f"向量检索出错: {vector_result}")
            
            if combined_memories:
                # 转换为列表并去重
                return list(combined_memories)
            
            return None
            
        except Exception as e:
            logger.error(f"混合检索失败: {e}")
            return None


class HybridInstantMemory:
    """混合瞬时记忆系统 V2
    
    智能融合LLM和向量两种记忆策略：
    - 快速内容使用向量系统V2 (自动清理过期记忆)
    - 复杂内容使用LLM系统
    - 重要内容双重备份
    - 统一检索接口
    - 支持相似度搜索和时间感知记忆
    """
    
    def __init__(self, chat_id: str, retention_hours: int = 24):
        self.chat_id = chat_id
        self.retention_hours = retention_hours
        
        # 初始化两个子系统
        self.llm_memory = InstantMemory(chat_id)
        self.vector_memory = VectorInstantMemoryV2(chat_id, retention_hours)
        
        # 初始化策略组件
        self.strategy = MemoryStrategy()
        self.sync = MemorySync(self.llm_memory, self.vector_memory)
        self.retriever = HybridRetriever(self.llm_memory, self.vector_memory)
        
        logger.info(f"混合瞬时记忆系统初始化完成: {chat_id} (向量保留{retention_hours}小时)")
    
    async def create_and_store_memory(self, text: str) -> None:
        """智能创建和存储记忆"""
        if not text.strip():
            return
        
        try:
            # 1. 策略决策
            decision = self.strategy.decide_strategy(text)
            
            logger.debug(f"记忆策略: {decision.mode.value} (置信度: {decision.confidence:.2f}) - {decision.reason}")
            
            # 2. 根据策略执行存储
            if decision.mode == MemoryMode.VECTOR_ONLY:
                await self._store_vector_only(text)
                
            elif decision.mode == MemoryMode.LLM_ONLY:
                await self._store_llm_only(text)
                
            elif decision.mode == MemoryMode.LLM_PREFERRED:
                await self._store_llm_preferred(text)
                
            elif decision.mode == MemoryMode.HYBRID:
                await self._store_hybrid(text)
            
        except Exception as e:
            logger.error(f"混合记忆存储失败: {e}")
    
    async def _store_vector_only(self, text: str):
        """仅向量存储"""
        await self.vector_memory.store_message(text)
    
    async def _store_llm_only(self, text: str):
        """仅LLM存储"""
        await self.llm_memory.create_and_store_memory(text)
    
    async def _store_llm_preferred(self, text: str):
        """LLM优先存储，向量备份"""
        try:
            # 主存储：LLM系统
            await self.llm_memory.create_and_store_memory(text)
            
            # 异步备份到向量系统
            asyncio.create_task(self.vector_memory.store_message(text))
            
        except Exception as e:
            logger.error(f"LLM优先存储失败，降级到向量系统: {e}")
            await self.vector_memory.store_message(text)
    
    async def _store_hybrid(self, text: str):
        """混合存储 - 并行存储到两个系统"""
        try:
            await asyncio.gather(
                self.llm_memory.create_and_store_memory(text),
                self.vector_memory.store_message(text),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"混合存储失败: {e}")
    
    async def get_memory(self, target: str) -> Optional[Union[str, List[str]]]:
        """统一记忆检索接口"""
        if not target.strip():
            return None
        
        try:
            # 根据查询复杂度选择检索策略
            query_decision = self.strategy.decide_strategy(target)
            
            # 对于查询，更偏向混合检索以获得更全面的结果
            if query_decision.mode == MemoryMode.VECTOR_ONLY and len(target) > 30:
                query_decision.mode = MemoryMode.HYBRID
            
            logger.debug(f"检索策略: {query_decision.mode.value} - {query_decision.reason}")
            
            return await self.retriever.retrieve_memories(target, query_decision.mode)
            
        except Exception as e:
            logger.error(f"混合记忆检索失败: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        llm_stats = {"total_memories": 0}  # LLM系统暂无统计接口
        vector_stats = self.vector_memory.get_stats()
        
        return {
            "chat_id": self.chat_id,
            "mode": "hybrid",
            "retention_hours": self.retention_hours,
            "llm_system": llm_stats,
            "vector_system": vector_stats,
            "strategy_patterns": {
                "emotional_keywords": len(self.strategy.emotional_keywords),
                "important_keywords": len(self.strategy.important_keywords)
            }
        }
    
    async def sync_memories(self, direction: str = "both"):
        """手动同步记忆"""
        try:
            if direction in ["both", "llm_to_vector"]:
                # LLM -> 向量的同步需要额外实现
                logger.info("LLM到向量的同步需要进一步开发")
                
            if direction in ["both", "vector_to_llm"]:
                # 向量 -> LLM的同步也需要额外实现
                logger.info("向量到LLM的同步需要进一步开发")
                
        except Exception as e:
            logger.error(f"记忆同步失败: {e}")
    
    def stop(self):
        """停止混合记忆系统"""
        try:
            self.vector_memory.stop()
            logger.info(f"混合瞬时记忆系统已停止: {self.chat_id}")
        except Exception as e:
            logger.error(f"停止混合记忆系统失败: {e}")
    
    async def find_similar_memories(self, query: str, top_k: int = 5, similarity_threshold: float = 0.7):
        """查找相似记忆 - 利用V2系统的新功能"""
        return await self.vector_memory.find_similar_messages(query, top_k, similarity_threshold)


# 为了保持向后兼容，提供快捷创建函数
def create_hybrid_memory(chat_id: str, retention_hours: int = 24) -> HybridInstantMemory:
    """创建混合瞬时记忆系统实例
    
    Args:
        chat_id: 聊天ID
        retention_hours: 向量记忆保留时长(小时)，默认24小时
    """
    return HybridInstantMemory(chat_id, retention_hours)