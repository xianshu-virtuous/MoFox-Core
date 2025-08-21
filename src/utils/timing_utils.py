#!/usr/bin/env python3
"""
时间间隔工具函数
用于主动思考功能的正态分布时间计算，支持3-sigma规则
"""

import random
import numpy as np
from typing import Optional


def get_normal_distributed_interval(
    base_interval: int, 
    sigma_percentage: float = 0.1,
    min_interval: Optional[int] = None,
    max_interval: Optional[int] = None,
    use_3sigma_rule: bool = True
) -> int:
    """
    获取符合正态分布的时间间隔，基于3-sigma规则
    
    Args:
        base_interval: 基础时间间隔（秒），作为正态分布的均值μ
        sigma_percentage: 标准差占基础间隔的百分比，默认10%
        min_interval: 最小间隔时间（秒），防止间隔过短
        max_interval: 最大间隔时间（秒），防止间隔过长
        use_3sigma_rule: 是否使用3-sigma规则限制分布范围，默认True
        
    Returns:
        int: 符合正态分布的时间间隔（秒）
        
    Example:
        >>> # 基础间隔1500秒（25分钟），标准差为150秒（10%）
        >>> interval = get_normal_distributed_interval(1500, 0.1)
        >>> # 99.7%的值会在μ±3σ范围内：1500±450 = [1050,1950]
    """
    # 🚨 基本输入保护：处理负数
    if base_interval < 0:
        base_interval = abs(base_interval)
    
    if sigma_percentage < 0:
        sigma_percentage = abs(sigma_percentage)
    
    # 特殊情况：基础间隔为0，使用纯随机模式
    if base_interval == 0:
        if sigma_percentage == 0:
            return 1  # 都为0时返回1秒
        return _generate_pure_random_interval(sigma_percentage, min_interval, max_interval, use_3sigma_rule)
    
    # 特殊情况：sigma为0，返回固定间隔
    if sigma_percentage == 0:
        return base_interval
    
    # 计算标准差
    sigma = base_interval * sigma_percentage
    
    # 📊 3-sigma规则：99.7%的数据落在μ±3σ范围内
    if use_3sigma_rule:
        three_sigma_min = base_interval - 3 * sigma
        three_sigma_max = base_interval + 3 * sigma
        
        # 确保3-sigma边界合理
        three_sigma_min = max(1, three_sigma_min)  # 最小1秒
        three_sigma_max = max(three_sigma_min + 1, three_sigma_max)  # 确保max > min
        
        # 应用用户设定的边界（如果更严格的话）
        if min_interval is not None:
            three_sigma_min = max(three_sigma_min, min_interval)
        if max_interval is not None:
            three_sigma_max = min(three_sigma_max, max_interval)
        
        effective_min = int(three_sigma_min)
        effective_max = int(three_sigma_max)
    else:
        # 不使用3-sigma规则，使用更宽松的边界
        effective_min = max(1, min_interval or 1)
        effective_max = max(effective_min + 1, max_interval or int(base_interval * 50))
    
    # 🎲 生成正态分布随机数
    max_attempts = 50  # 3-sigma规则下成功率约99.7%，50次足够了
    
    for attempt in range(max_attempts):
        # 生成正态分布值
        value = np.random.normal(loc=base_interval, scale=sigma)
        
        # 💡 关键：对负数取绝对值，保持分布特性
        if value < 0:
            value = abs(value)
        
        # 转换为整数
        interval = int(round(value))
        
        # 检查是否在有效范围内
        if effective_min <= interval <= effective_max:
            return interval
    
    # 如果50次都没成功，返回3-sigma范围内的随机值
    return int(np.random.uniform(effective_min, effective_max))


def _generate_pure_random_interval(
    sigma_percentage: float, 
    min_interval: Optional[int] = None, 
    max_interval: Optional[int] = None,
    use_3sigma_rule: bool = True
) -> int:
    """
    当base_interval=0时的纯随机模式，基于3-sigma规则
    
    Args:
        sigma_percentage: 标准差百分比，将被转换为实际时间值
        min_interval: 最小间隔
        max_interval: 最大间隔
        use_3sigma_rule: 是否使用3-sigma规则
        
    Returns:
        int: 随机生成的时间间隔（秒）
    """
    # 将百分比转换为实际时间值（假设1000秒作为基准）
    # sigma_percentage=0.3 -> sigma=300秒
    base_reference = 1000  # 基准时间
    sigma = abs(sigma_percentage) * base_reference
    
    # 使用sigma作为均值，sigma/3作为标准差
    # 这样3σ范围约为[0, 2*sigma]
    mean = sigma
    std = sigma / 3  
    
    if use_3sigma_rule:
        # 3-sigma边界：μ±3σ = sigma±3*(sigma/3) = sigma±sigma = [0, 2*sigma]
        three_sigma_min = max(1, mean - 3 * std)  # 理论上约为0，但最小1秒
        three_sigma_max = mean + 3 * std  # 约为2*sigma
        
        # 应用用户边界
        if min_interval is not None:
            three_sigma_min = max(three_sigma_min, min_interval)
        if max_interval is not None:
            three_sigma_max = min(three_sigma_max, max_interval)
            three_sigma_min = max(three_sigma_min, min_interval)
        if max_interval is not None:
            three_sigma_max = min(three_sigma_max, max_interval)
        
        effective_min = int(three_sigma_min)
        effective_max = int(three_sigma_max)
    else:
        # 不使用3-sigma规则
        effective_min = max(1, min_interval or 1)
        effective_max = max(effective_min + 1, max_interval or int(mean * 10))
    
    # 生成随机值
    for _ in range(50):
        value = np.random.normal(loc=mean, scale=std)
        
        # 对负数取绝对值
        if value < 0:
            value = abs(value)
            
        interval = int(round(value))
        
        if effective_min <= interval <= effective_max:
            return interval
    
    # 备用方案
    return int(np.random.uniform(effective_min, effective_max))


def format_time_duration(seconds: int) -> str:
    """
    将秒数格式化为易读的时间格式
    
    Args:
        seconds: 秒数
        
    Returns:
        str: 格式化的时间字符串，如"2小时30分15秒"
    """
    if seconds < 60:
        return f"{seconds}秒"
    
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    
    if minutes < 60:
        if remaining_seconds > 0:
            return f"{minutes}分{remaining_seconds}秒"
        else:
            return f"{minutes}分"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if hours < 24:
        if remaining_minutes > 0 and remaining_seconds > 0:
            return f"{hours}小时{remaining_minutes}分{remaining_seconds}秒"
        elif remaining_minutes > 0:
            return f"{hours}小时{remaining_minutes}分"
        else:
            return f"{hours}小时"
    
    days = hours // 24
    remaining_hours = hours % 24
    
    if remaining_hours > 0:
        return f"{days}天{remaining_hours}小时"
    else:
        return f"{days}天"