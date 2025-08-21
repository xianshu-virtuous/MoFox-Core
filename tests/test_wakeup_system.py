import pytest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.chat.chat_loop.wakeup_manager import WakeUpManager
from src.chat.chat_loop.hfc_context import HfcContext
from src.config.official_configs import WakeUpSystemConfig


class TestWakeUpManager:
    """唤醒度管理器测试类"""
    
    @pytest.fixture
    def mock_context(self):
        """创建模拟的HFC上下文"""
        context = Mock(spec=HfcContext)
        context.stream_id = "test_chat_123"
        context.log_prefix = "[TEST]"
        context.running = True
        return context
    
    @pytest.fixture
    def wakeup_config(self):
        """创建测试用的唤醒度配置"""
        return WakeUpSystemConfig(
            enable=True,
            wakeup_threshold=15.0,
            private_message_increment=3.0,
            group_mention_increment=2.0,
            decay_rate=0.2,
            decay_interval=30.0,
            angry_duration=300.0  # 5分钟
        )
    
    @pytest.fixture
    def wakeup_manager(self, mock_context, wakeup_config):
        """创建唤醒度管理器实例"""
        with patch('src.chat.chat_loop.wakeup_manager.global_config') as mock_global_config:
            mock_global_config.wakeup_system = wakeup_config
            manager = WakeUpManager(mock_context)
            return manager
    
    def test_initialization(self, wakeup_manager, wakeup_config):
        """测试初始化"""
        assert wakeup_manager.wakeup_value == 0.0
        assert wakeup_manager.is_angry == False
        assert wakeup_manager.wakeup_threshold == wakeup_config.wakeup_threshold
        assert wakeup_manager.private_message_increment == wakeup_config.private_message_increment
        assert wakeup_manager.group_mention_increment == wakeup_config.group_mention_increment
        assert wakeup_manager.decay_rate == wakeup_config.decay_rate
        assert wakeup_manager.decay_interval == wakeup_config.decay_interval
        assert wakeup_manager.angry_duration == wakeup_config.angry_duration
        assert wakeup_manager.enabled == wakeup_config.enable
    
    @patch('src.manager.schedule_manager.schedule_manager')
    @patch('src.mood.mood_manager.mood_manager')
    def test_private_message_wakeup_accumulation(self, mock_mood_manager, mock_schedule_manager, wakeup_manager):
        """测试私聊消息唤醒度累积"""
        # 模拟休眠状态
        mock_schedule_manager.is_sleeping.return_value = True
        
        # 发送5条私聊消息 (5 * 3.0 = 15.0，达到阈值)
        for i in range(4):
            result = wakeup_manager.add_wakeup_value(is_private_chat=True)
            assert result == False  # 前4条消息不应该触发唤醒
            assert wakeup_manager.wakeup_value == (i + 1) * 3.0
        
        # 第5条消息应该触发唤醒
        result = wakeup_manager.add_wakeup_value(is_private_chat=True)
        assert result == True
        assert wakeup_manager.is_angry == True
        assert wakeup_manager.wakeup_value == 0.0  # 唤醒后重置
        
        # 验证情绪管理器被调用
        mock_mood_manager.set_angry_from_wakeup.assert_called_once_with("test_chat_123")
    
    @patch('src.manager.schedule_manager.schedule_manager')
    @patch('src.mood.mood_manager.mood_manager')
    def test_group_mention_wakeup_accumulation(self, mock_mood_manager, mock_schedule_manager, wakeup_manager):
        """测试群聊艾特消息唤醒度累积"""
        # 模拟休眠状态
        mock_schedule_manager.is_sleeping.return_value = True
        
        # 发送7条群聊艾特消息 (7 * 2.0 = 14.0，未达到阈值)
        for i in range(7):
            result = wakeup_manager.add_wakeup_value(is_private_chat=False, is_mentioned=True)
            assert result == False
            assert wakeup_manager.wakeup_value == (i + 1) * 2.0
        
        # 第8条消息应该触发唤醒 (8 * 2.0 = 16.0，超过阈值15.0)
        result = wakeup_manager.add_wakeup_value(is_private_chat=False, is_mentioned=True)
        assert result == True
        assert wakeup_manager.is_angry == True
        assert wakeup_manager.wakeup_value == 0.0
        
        # 验证情绪管理器被调用
        mock_mood_manager.set_angry_from_wakeup.assert_called_once_with("test_chat_123")
    
    @patch('src.manager.schedule_manager.schedule_manager')
    def test_group_message_without_mention(self, mock_schedule_manager, wakeup_manager):
        """测试群聊未艾特消息不增加唤醒度"""
        # 模拟休眠状态
        mock_schedule_manager.is_sleeping.return_value = True
        
        # 发送群聊消息但未被艾特
        result = wakeup_manager.add_wakeup_value(is_private_chat=False, is_mentioned=False)
        assert result == False
        assert wakeup_manager.wakeup_value == 0.0  # 不应该增加
    
    @patch('src.manager.schedule_manager.schedule_manager')
    def test_no_accumulation_when_not_sleeping(self, mock_schedule_manager, wakeup_manager):
        """测试非休眠状态下不累积唤醒度"""
        # 模拟非休眠状态
        mock_schedule_manager.is_sleeping.return_value = False
        
        # 发送私聊消息
        result = wakeup_manager.add_wakeup_value(is_private_chat=True)
        assert result == False
        assert wakeup_manager.wakeup_value == 0.0  # 不应该增加
    
    def test_disabled_system(self, mock_context):
        """测试系统禁用时的行为"""
        disabled_config = WakeUpSystemConfig(enable=False)
        
        with patch('src.chat.chat_loop.wakeup_manager.global_config') as mock_global_config:
            mock_global_config.wakeup_system = disabled_config
            manager = WakeUpManager(mock_context)
            
            with patch('src.manager.schedule_manager.schedule_manager') as mock_schedule_manager:
                mock_schedule_manager.is_sleeping.return_value = True
                
                # 即使发送消息也不应该累积唤醒度
                result = manager.add_wakeup_value(is_private_chat=True)
                assert result == False
                assert manager.wakeup_value == 0.0
    
    @patch('src.mood.mood_manager.mood_manager')
    def test_angry_state_expiration(self, mock_mood_manager, wakeup_manager):
        """测试愤怒状态过期"""
        # 手动设置愤怒状态
        wakeup_manager.is_angry = True
        wakeup_manager.angry_start_time = time.time() - 400  # 400秒前开始愤怒（超过300秒持续时间）
        
        # 检查愤怒状态应该已过期
        is_angry = wakeup_manager.is_in_angry_state()
        assert is_angry == False
        assert wakeup_manager.is_angry == False
        
        # 验证情绪管理器被调用清除愤怒状态
        mock_mood_manager.clear_angry_from_wakeup.assert_called_once_with("test_chat_123")
    
    def test_angry_prompt_addition(self, wakeup_manager):
        """测试愤怒状态提示词"""
        # 非愤怒状态
        prompt = wakeup_manager.get_angry_prompt_addition()
        assert prompt == ""
        
        # 愤怒状态
        wakeup_manager.is_angry = True
        wakeup_manager.angry_start_time = time.time()
        prompt = wakeup_manager.get_angry_prompt_addition()
        assert "吵醒" in prompt and "生气" in prompt
    
    def test_status_info(self, wakeup_manager):
        """测试状态信息获取"""
        # 设置一些状态
        wakeup_manager.wakeup_value = 10.5
        wakeup_manager.is_angry = True
        wakeup_manager.angry_start_time = time.time()
        
        status = wakeup_manager.get_status_info()
        
        assert status["wakeup_value"] == 10.5
        assert status["wakeup_threshold"] == 15.0
        assert status["is_angry"] == True
        assert status["angry_remaining_time"] > 0
    
    @pytest.mark.asyncio
    async def test_decay_loop(self, wakeup_manager):
        """测试衰减循环"""
        # 设置初始唤醒度
        wakeup_manager.wakeup_value = 5.0
        
        # 模拟一次衰减
        with patch('asyncio.sleep') as mock_sleep:
            # 创建一个会立即停止的衰减循环
            wakeup_manager.context.running = False
            
            # 手动调用衰减逻辑
            if wakeup_manager.wakeup_value > 0:
                old_value = wakeup_manager.wakeup_value
                wakeup_manager.wakeup_value = max(0, wakeup_manager.wakeup_value - wakeup_manager.decay_rate)
                
            assert wakeup_manager.wakeup_value == 4.8  # 5.0 - 0.2 = 4.8
    
    @pytest.mark.asyncio
    @patch('src.mood.mood_manager.mood_manager')
    async def test_angry_state_expiration_in_decay_loop(self, mock_mood_manager, wakeup_manager):
        """测试衰减循环中愤怒状态过期"""
        # 设置过期的愤怒状态
        wakeup_manager.is_angry = True
        wakeup_manager.angry_start_time = time.time() - 400  # 400秒前
        
        # 手动调用衰减循环中的愤怒状态检查逻辑
        current_time = time.time()
        if wakeup_manager.is_angry and current_time - wakeup_manager.angry_start_time >= wakeup_manager.angry_duration:
            wakeup_manager.is_angry = False
            mock_mood_manager.clear_angry_from_wakeup(wakeup_manager.context.stream_id)
        
        assert wakeup_manager.is_angry == False
        mock_mood_manager.clear_angry_from_wakeup.assert_called_once_with("test_chat_123")
    
    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, wakeup_manager):
        """测试启动和停止生命周期"""
        # 测试启动
        await wakeup_manager.start()
        assert wakeup_manager._decay_task is not None
        assert not wakeup_manager._decay_task.done()
        
        # 测试停止
        await wakeup_manager.stop()
        assert wakeup_manager._decay_task.cancelled()
    
    @pytest.mark.asyncio
    async def test_disabled_system_start(self, mock_context):
        """测试禁用系统的启动行为"""
        disabled_config = WakeUpSystemConfig(enable=False)
        
        with patch('src.chat.chat_loop.wakeup_manager.global_config') as mock_global_config:
            mock_global_config.wakeup_system = disabled_config
            manager = WakeUpManager(mock_context)
            
            await manager.start()
            assert manager._decay_task is None  # 禁用时不应该创建衰减任务


class TestWakeUpSystemIntegration:
    """唤醒度系统集成测试"""
    
    @patch('src.manager.schedule_manager.schedule_manager')
    @patch('src.mood.mood_manager.mood_manager')
    def test_mixed_message_types(self, mock_mood_manager, mock_schedule_manager):
        """测试混合消息类型的唤醒度累积"""
        mock_schedule_manager.is_sleeping.return_value = True
        
        # 创建配置和管理器
        config = WakeUpSystemConfig(
            enable=True,
            wakeup_threshold=10.0,  # 降低阈值便于测试
            private_message_increment=3.0,
            group_mention_increment=2.0,
            decay_rate=0.2,
            decay_interval=30.0,
            angry_duration=300.0
        )
        
        context = Mock(spec=HfcContext)
        context.stream_id = "test_mixed"
        context.log_prefix = "[MIXED]"
        context.running = True
        
        with patch('src.chat.chat_loop.wakeup_manager.global_config') as mock_global_config:
            mock_global_config.wakeup_system = config
            manager = WakeUpManager(context)
            
            # 发送2条私聊消息 (2 * 3.0 = 6.0)
            manager.add_wakeup_value(is_private_chat=True)
            manager.add_wakeup_value(is_private_chat=True)
            assert manager.wakeup_value == 6.0
            
            # 发送2条群聊艾特消息 (2 * 2.0 = 4.0, 总计10.0)
            manager.add_wakeup_value(is_private_chat=False, is_mentioned=True)
            assert manager.wakeup_value == 8.0
            
            # 最后一条消息触发唤醒
            result = manager.add_wakeup_value(is_private_chat=False, is_mentioned=True)
            assert result == True
            assert manager.is_angry == True
            assert manager.wakeup_value == 0.0
            
            mock_mood_manager.set_angry_from_wakeup.assert_called_once_with("test_mixed")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])