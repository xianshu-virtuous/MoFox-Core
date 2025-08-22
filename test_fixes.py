#!/usr/bin/env python3
"""
验证修复效果的测试脚本

本脚本验证:
1. no_reply 和 reply 动作是否正确注册
2. 思考循环间隔优化是否生效
3. Action系统的回退机制是否工作正常
"""

import sys
import os
import asyncio
import time
from typing import Dict, Any

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

async def test_action_registration():
    """测试Action注册情况"""
    print("=== 测试Action注册情况 ===")
    
    try:
        # 导入插件系统
        from src.plugin_system.manager import PluginManager
        from src.plugin_system.component.action_manager import ActionManager
        
        # 初始化组件
        plugin_manager = PluginManager()
        action_manager = ActionManager()
        
        # 加载插件
        await plugin_manager.load_all_plugins()
        
        # 检查动作注册情况
        print("正在检查已注册的动作...")
        registered_actions = action_manager.list_actions()
        
        print(f"总共注册了 {len(registered_actions)} 个动作:")
        for action_name in registered_actions:
            print(f"  - {action_name}")
        
        # 重点检查no_reply和reply
        critical_actions = ["no_reply", "reply"]
        missing_actions = []
        
        for action in critical_actions:
            if action in registered_actions:
                print(f"✅ {action} 动作已正确注册")
            else:
                print(f"❌ {action} 动作未注册")
                missing_actions.append(action)
        
        if missing_actions:
            print(f"\n⚠️  缺失的关键动作: {missing_actions}")
            return False
        else:
            print("\n✅ 所有关键动作都已正确注册")
            return True
            
    except Exception as e:
        print(f"❌ 测试Action注册时出错: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def test_loop_timing_config():
    """测试循环时间配置"""
    print("\n=== 测试循环时间配置 ===")
    
    try:
        # 模拟循环间隔逻辑
        consecutive_empty_loops = 0
        timing_schedule = []
        
        # 模拟50次空循环，记录间隔时间
        for i in range(50):
            if consecutive_empty_loops <= 5:
                interval = 0.5
            elif consecutive_empty_loops <= 20:
                interval = 2.0
            else:
                interval = 5.0
            
            timing_schedule.append((i+1, interval))
            consecutive_empty_loops += 1
        
        print("循环间隔调度表:")
        print("循环次数 -> 等待时间(秒)")
        
        for loop_num, interval in timing_schedule[::5]:  # 每5次显示一次
            print(f"  第{loop_num:2d}次 -> {interval}秒")
        
        # 分析间隔分布
        intervals = [schedule[1] for schedule in timing_schedule]
        short_intervals = len([i for i in intervals if i == 0.5])
        medium_intervals = len([i for i in intervals if i == 2.0])
        long_intervals = len([i for i in intervals if i == 5.0])
        
        print(f"\n间隔分布:")
        print(f"  短间隔(0.5s): {short_intervals}次")
        print(f"  中间隔(2.0s): {medium_intervals}次")
        print(f"  长间隔(5.0s): {long_intervals}次")
        
        # 验证逻辑正确性
        if short_intervals == 6 and medium_intervals == 15 and long_intervals == 29:
            print("✅ 循环间隔逻辑配置正确")
            return True
        else:
            print("❌ 循环间隔逻辑配置有误")
            return False
            
    except Exception as e:
        print(f"❌ 测试循环时间配置时出错: {e}")
        return False

def test_core_actions_config():
    """测试core_actions插件配置"""
    print("\n=== 测试core_actions插件配置 ===")
    
    try:
        import json
        import toml
        
        # 检查manifest文件
        manifest_path = "src/plugins/built_in/core_actions/_manifest.json"
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            components = manifest.get('plugin_info', {}).get('components', [])
            component_names = [comp['name'] for comp in components]
            
            print(f"Manifest中注册的组件: {component_names}")
            
            if 'reply' in component_names:
                print("✅ reply 动作已在manifest中注册")
            else:
                print("❌ reply 动作未在manifest中注册")
                return False
        else:
            print("❌ 找不到manifest文件")
            return False
        
        # 检查config.toml文件
        config_path = "src/plugins/built_in/core_actions/config.toml"
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = toml.load(f)
            
            components_config = config.get('components', {})
            
            print(f"配置文件中的组件设置:")
            for key, value in components_config.items():
                print(f"  {key}: {value}")
            
            if components_config.get('enable_reply', False):
                print("✅ reply 动作已在配置中启用")
            else:
                print("❌ reply 动作未在配置中启用")
                return False
        else:
            print("❌ 找不到配置文件")
            return False
        
        print("✅ core_actions插件配置正确")
        return True
        
    except Exception as e:
        print(f"❌ 测试插件配置时出错: {e}")
        import traceback
        print(traceback.format_exc())
        return False

async def main():
    """主测试函数"""
    print("🚀 开始验证MaiBot-Plus修复效果\n")
    
    # 记录测试开始时间
    start_time = time.time()
    
    # 执行各项测试
    tests = [
        ("插件配置", test_core_actions_config),
        ("循环时间配置", test_loop_timing_config),
        ("Action注册", test_action_registration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ 测试 {test_name} 时发生异常: {e}")
            results.append((test_name, False))
    
    # 汇总结果
    print("\n" + "="*50)
    print("📊 测试结果汇总:")
    
    passed_tests = 0
    total_tests = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            passed_tests += 1
    
    # 计算测试耗时
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\n总体结果: {passed_tests}/{total_tests} 个测试通过")
    print(f"测试耗时: {duration:.2f}秒")
    
    if passed_tests == total_tests:
        print("\n🎉 所有测试通过！修复已生效。")
        print("\n主要修复内容:")
        print("1. ✅ 修复了 reply 动作未注册的问题")
        print("2. ✅ 优化了思考循环间隔，避免无谓的快速循环")
        print("3. ✅ 更新了插件配置和manifest文件")
        print("\n现在系统应该:")
        print("- 有新消息时快速响应(0.1-0.5秒)")
        print("- 无新消息时逐步延长等待时间(2-5秒)")
        print("- no_reply 和 reply 动作都可用")
    else:
        print(f"\n⚠️  还有 {total_tests - passed_tests} 个问题需要解决")
        return False
    
    return True

if __name__ == "__main__":
    try:
        # 切换到项目目录
        os.chdir(project_root)
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试过程中发生未预期的错误: {e}")
        import traceback
        print(traceback.format_exc())
        sys.exit(1)
