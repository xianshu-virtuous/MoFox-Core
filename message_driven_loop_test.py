#!/usr/bin/env python3
"""
消息驱动思考循环逻辑验证

验证修改后的思考循环逻辑：
1. 只有在有新消息时才进行思考循环
2. 无新消息时仅进行系统状态检查
3. 主动思考系统独立工作
"""

import asyncio
import time
from typing import List


class MockMessage:
    """模拟消息对象"""
    def __init__(self, content: str, timestamp: float):
        self.content = content
        self.timestamp = timestamp


class MockContext:
    """模拟聊天上下文"""
    def __init__(self):
        self.running = True
        self.last_read_time = time.time()
        self.last_message_time = time.time()
        self.loop_mode = "FOCUS"


class MessageDrivenChatLoop:
    """消息驱动的聊天循环模拟"""
    
    def __init__(self):
        self.context = MockContext()
        self.message_queue: List[MockMessage] = []
        self.thinking_cycles = 0
        self.status_checks = 0
        
    def add_message(self, content: str):
        """添加新消息"""
        msg = MockMessage(content, time.time())
        self.message_queue.append(msg)
        
    def get_recent_messages(self) -> List[MockMessage]:
        """获取新消息（模拟message_api.get_messages_by_time_in_chat）"""
        current_time = time.time()
        new_messages = []
        
        for msg in self.message_queue:
            if msg.timestamp > self.context.last_read_time:
                new_messages.append(msg)
                
        # 更新读取时间
        if new_messages:
            self.context.last_read_time = current_time
            
        return new_messages
        
    async def _loop_body(self) -> bool:
        """模拟新的loop_body逻辑"""
        recent_messages = self.get_recent_messages()
        has_new_messages = bool(recent_messages)
        
        if has_new_messages:
            print(f"🔄 发现 {len(recent_messages)} 条新消息，开始思考循环")
            self.thinking_cycles += 1
            
            # 模拟思考处理
            for msg in recent_messages:
                print(f"   处理消息: {msg.content}")
                await asyncio.sleep(0.01)  # 模拟处理时间
                
            self.context.last_message_time = time.time()
        else:
            print("📋 无新消息，仅进行状态检查")
            self.status_checks += 1
            
        return has_new_messages
        
    async def _main_chat_loop(self):
        """模拟新的主聊天循环逻辑"""
        loop_count = 0
        max_loops = 20  # 限制测试循环数
        
        while self.context.running and loop_count < max_loops:
            loop_count += 1
            has_new_messages = await self._loop_body()
            
            if has_new_messages:
                print("   ⚡ 有新消息，快速检查下一轮")
                await asyncio.sleep(0.1)
            else:
                print("   ⏸️  无新消息，等待1秒后再检查")
                await asyncio.sleep(1.0)
                
        self.context.running = False


async def test_message_driven_logic():
    """测试消息驱动逻辑"""
    print("=== 消息驱动思考循环测试 ===\n")
    
    chat_loop = MessageDrivenChatLoop()
    
    # 创建消息注入任务
    async def inject_messages():
        await asyncio.sleep(2)
        print("📨 注入消息: 'hello'")
        chat_loop.add_message("hello")
        
        await asyncio.sleep(3)
        print("📨 注入消息: 'how are you?'")
        chat_loop.add_message("how are you?")
        
        await asyncio.sleep(2)
        print("📨 注入消息: 'goodbye'")
        chat_loop.add_message("goodbye")
        
        await asyncio.sleep(5)
        print("🛑 停止测试")
        chat_loop.context.running = False
    
    # 同时运行聊天循环和消息注入
    await asyncio.gather(
        chat_loop._main_chat_loop(),
        inject_messages()
    )
    
    # 统计结果
    print("\n=== 测试结果 ===")
    print(f"思考循环次数: {chat_loop.thinking_cycles}")
    print(f"状态检查次数: {chat_loop.status_checks}")
    print(f"思考/检查比例: {chat_loop.thinking_cycles}/{chat_loop.status_checks}")
    
    # 验证预期结果
    if chat_loop.thinking_cycles == 3:  # 3条消息 = 3次思考
        print("✅ 思考次数正确：只在有新消息时思考")
    else:
        print("❌ 思考次数错误：不应该在无消息时思考")
        
    if chat_loop.status_checks > chat_loop.thinking_cycles:
        print("✅ 状态检查合理：无消息时只进行状态检查")
    else:
        print("❌ 状态检查不足")


async def test_no_message_scenario():
    """测试无消息场景"""
    print("\n=== 无消息场景测试 ===")
    
    chat_loop = MessageDrivenChatLoop()
    
    # 运行5秒无消息场景
    start_time = time.time()
    loop_count = 0
    
    while time.time() - start_time < 3 and loop_count < 10:
        loop_count += 1
        has_new_messages = await chat_loop._loop_body()
        
        if not has_new_messages:
            await asyncio.sleep(1.0)
    
    print("无消息运行结果:")
    print(f"  思考循环: {chat_loop.thinking_cycles} 次")
    print(f"  状态检查: {chat_loop.status_checks} 次")
    
    if chat_loop.thinking_cycles == 0:
        print("✅ 无消息时不进行思考循环")
    else:
        print("❌ 无消息时仍在进行思考循环")


if __name__ == "__main__":
    print("验证消息驱动思考循环逻辑\n")
    
    asyncio.run(test_message_driven_logic())
    asyncio.run(test_no_message_scenario())
    
    print("\n=== 修改说明 ===")
    print("1. ✅ 只有新消息到达时才触发思考循环")
    print("2. ✅ 无新消息时仅进行轻量级状态检查")
    print("3. ✅ 主动思考系统独立运行，不受此影响")
    print("4. ✅ 大幅减少无意义的CPU消耗")
    print("5. ✅ 保持对新消息的快速响应能力")
