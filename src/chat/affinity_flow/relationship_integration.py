"""
回复后关系追踪集成初始化脚本

此脚本用于设置回复后关系追踪系统的全局变量和初始化连接
确保各组件能正确协同工作
"""

from src.chat.affinity_flow.relationship_tracker import UserRelationshipTracker
from src.chat.affinity_flow.interest_scoring import interest_scoring_system
from src.common.logger import get_logger

logger = get_logger("relationship_integration")

# 全局关系追踪器实例
relationship_tracker = None


def initialize_relationship_tracking():
    """初始化关系追踪系统"""
    global relationship_tracker

    try:
        logger.info("🚀 初始化回复后关系追踪系统...")

        # 创建关系追踪器实例
        relationship_tracker = UserRelationshipTracker(interest_scoring_system=interest_scoring_system)

        # 设置兴趣度评分系统的关系追踪器引用
        interest_scoring_system.relationship_tracker = relationship_tracker

        logger.info("✅ 回复后关系追踪系统初始化完成")
        logger.info("📋 系统功能:")
        logger.info("   🔄 自动回复后关系追踪")
        logger.info("   💾 数据库持久化存储")
        logger.info("   🧠 LLM智能关系分析")
        logger.info("   ⏰ 5分钟追踪间隔")
        logger.info("   🎯 兴趣度评分集成")

        return relationship_tracker

    except Exception as e:
        logger.error(f"❌ 关系追踪系统初始化失败: {e}")
        logger.debug("错误详情:", exc_info=True)
        return None


def get_relationship_tracker():
    """获取全局关系追踪器实例"""
    global relationship_tracker
    return relationship_tracker


def setup_plan_executor_relationship_tracker(plan_executor):
    """为PlanExecutor设置关系追踪器"""
    global relationship_tracker

    if relationship_tracker and plan_executor:
        plan_executor.set_relationship_tracker(relationship_tracker)
        logger.info("✅ PlanExecutor关系追踪器设置完成")
        return True

    logger.warning("⚠️ 无法设置PlanExecutor关系追踪器")
    return False


# 自动初始化
if __name__ == "__main__":
    initialize_relationship_tracking()
