# 主动聊天功能重构与设计方案

本文档旨在规划一个全新的、真正的“主动发起对话”功能。方案的核心是创建一个独立的、可配置的插件，并重构现有配置，使其更具模块化和可扩展性。

## 1. 配置文件重构 (`bot_config.toml`)

为了提高清晰度和模块化，我们将创建一个新的配置节 `[proactive_thinking]`。

### 1.1. 移除旧配置

以下配置项将从 `[chat]` 配置节中 **移除**:

```toml
# mmc/config/bot_config.toml

# 从 line 132 开始移除以下所有行
talk_frequency_adjust = [['', '8:00,1', '12:00,1.2', '18:00,1.5', '01:00,0.6'], ['qq:114514:group', '12:20,1', '16:10,2', '20:10,1', '00:10,0.3'], ['qq:1919810:private', '8:20,1', '12:10,2', '20:10,1.5', '00:10,0.2']]
# ... (所有 talk_frequency_adjust 的注释) ...

# 主动思考功能配置（仅在focus模式下生效）

enable_proactive_thinking = false
proactive_thinking_interval = 1500
# ... (所有 proactive_thinking 的注释和相关配置) ...
delta_sigma = 120
# ... (所有 delta_sigma 的注释和相关配置) ...
```

### 1.2. 新增 `[proactive_thinking]` 配置节

在 `bot_config.toml` 文件 **末尾**，添加以下全新配置节：

```toml
# mmc/config/bot_config.toml

[proactive_thinking] # 主动思考（主动发起对话）功能配置
# --- 总开关 ---
enable = false # 是否启用主动发起对话功能

# --- 触发时机 ---
# 基础触发间隔（秒），AI会围绕这个时间点主动发起对话
interval = 1500 # 默认25分钟
# 间隔随机化标准差（秒），让触发时间更自然。设为0则为固定间隔。
interval_sigma = 120
# 每日活跃度调整，格式：[["", "HH:MM,factor", ...], ["stream_id", ...]]
# factor > 1.0 会缩短思考间隔，更活跃；factor < 1.0 会延长间隔。
talk_frequency_adjust = [['', '8:00,1', '12:00,1.2', '18:00,1.5', '01:00,0.6']]

# --- 作用范围 ---
enable_in_private = true # 是否允许在私聊中主动发起对话
enable_in_group = true # 是否允许在群聊中主动发起对话
# 私聊白名单，为空则对所有私聊生效
# 格式: ["platform:user_id", ...] e.g., ["qq:123456"]
enabled_private_chats = []
# 群聊白名单，为空则对所有群聊生效
# 格式: ["platform:group_id", ...] e.g., ["qq:7891011"]
enabled_group_chats = []

# --- 冷启动配置 (针对私聊) ---
# 对于白名单中不活跃的私聊，是否允许进行一次“冷启动”问候
enable_cold_start = true
# 冷启动后，该私聊的下一次主动思考需要等待的最小时间（秒）
cold_start_cooldown = 86400 # 默认24小时
```

## 2. 新插件架构设计 (`proactive_initiation_chatter`)

我们将创建一个全新的插件来实现此功能。

### 2.1. 文件结构

```
mmc/src/plugins/built_in/proactive_initiation_chatter/
├── __init__.py
├── _manifest.json
├── plugin.py                 # 插件主入口，负责启动和管理触发器
├── trigger_manager.py        # 核心触发器，内置于插件中
├── initiation_chatter.py     # Chatter实现，监听触发事件
└── initiation_planner.py     # 规划器，负责决定“说什么”
```

### 2.2. 核心组件设计

#### `plugin.py` - `ProactiveInitiationPlugin`
- **职责**: 作为插件的入口，它将在插件被加载时，读取 `[proactive_thinking]` 配置，并根据配置启动 `ProactiveTriggerManager`。
- **启动逻辑 (参考 `maizone_refactored`)**:

#### `trigger_manager.py` - `ProactiveTriggerManager`
- **职责**: 这是一个后台服务类，负责管理所有聊天流的触发计时器，并实现包括“冷启动”在内的所有复杂触发逻辑。
- **核心逻辑 (参考 `SchedulerService`)**:
  - 维护一个异步主循环，定期检查所有符合条件的聊天流。
  - 根据配置的间隔和活跃度调整，计算下次触发时间。
  - 在触发时，调用 `InitiationPlanner` 来决定具体内容，并通过事件管理器派发 `ProactiveInitiationEvent` 或 `ColdStartInitiationEvent`。

---

## 3. 核心交互与依赖

新的 `proactive_initiation_chatter` 插件将与以下核心系统模块进行交互，以确保其决策的智能性和合规性：

- **`Config`**: `TriggerManager` 和 `Planner` 将从全局配置中读取 `[proactive_thinking]` 配置节，以获取所有行为参数。
- **`EventManager`**: `TriggerManager` 将通过事件管理器派发 `ProactiveInitiationEvent` 和 `ColdStartInitiationEvent` 事件。`InitiationChatter` 则会监听这些事件以触发执行。
- **`AsyncTaskManager`**: `ProactiveInitiationPlugin` 将使用此管理器来安全地在后台运行 `TriggerManager` 的主循环。
- **`ChatManager` (from `chat_stream.py`)**: 这是实现“冷启动”的核心。`TriggerManager` 将调用 `chat_manager.get_or_create_stream()` 方法来按需“唤醒”或创建不活跃的聊天流实例及其附带的空上下文。
- **`SleepManager`**: 在每次触发决策前，`TriggerManager` **必须**查询 `SleepManager` 以确认AI当前未处于睡眠状态。
- **`ScheduleManager` / `MonthlyPlanManager`**: `InitiationPlanner` 的“待办任务驱动”策略会查询这些管理器，以获取可作为聊天话题的日程或计划。
- **`MemoryManager` / `ContextManager`**: `InitiationPlanner` 的“记忆驱动”策略会查询长期记忆和短期上下文，以寻找关联性话题。
- **`RelationshipManager`**: `InitiationPlanner` 可以查询关系分数，作为执行某些话题策略的门槛。

## 4. 插件清单文件 (`_manifest.json`)

插件的清单文件将定义其元数据和依赖。

```json
{
  "manifest_version": 1,
  "name": "ProactiveInitiationChatter",
  "version": "1.0.0",
  "author": "Kilo Code",
  "description": "一个真正的主动发起对话插件，由内置的、可高度配置的触发器驱动。",
  "dependencies": [],
  "python_dependencies": []
}
```

---

## 5. 上下文获取与“唤醒”机制详解

本设计区分了“热启动”（针对活跃聊天）和“冷启动”（针对非活跃聊天）两种场景，并利用 `ChatManager` 的不同方法来优雅地处理。

### 热启动流程 (Hot Start - 针对活跃聊天)

这是最常见的场景。当一个聊天流近期有过对话，其实例存在于 `ChatManager` 的内存缓存中。

1.  **获取现有上下文**: `ProactiveTriggerManager` 决定对一个活跃的 `stream_id` 发起对话时，它会调用 `chat_manager.get_stream(stream_id)`。
2.  **返回缓存实例**: `ChatManager` 会直接从内存中返回缓存的 `ChatStream` 实例。
3.  **传递丰富上下文**: 这个实例中包含了**完整的、包含近期对话历史**的 `stream_context`。
4.  **智能决策**: `TriggerManager` 将这个**充满信息**的上下文派发给 `InitiationPlanner`。`Planner` 因此可以优先使用“记忆驱动”等高级策略，生成与前文高度相关的话题，使对话显得自然、连贯。

### 冷启动流程 (Cold Start - “唤醒”非活跃聊天)

针对在白名单中，但当前未加载到内存的私聊。

**核心方法:** `ChatManager.get_or_create_stream(platform, user_info, group_info)`

**唤醒流程:**

1.  `ProactiveTriggerManager` 在主循环中识别到一个需要“冷启动”的私聊 `stream_id`。
2.  `TriggerManager` 构造出必要的 `UserInfo` 对象。
3.  它调用 `get_chat_manager()`，然后执行核心的唤醒调用:
    ```python
    # (伪代码)
    chat_stream = await chat_manager.get_or_create_stream(...)
    ```
4.  此调用会从数据库加载或全新创建一个 `ChatStream` 实例，该实例内部会自动创建一个**不包含任何历史消息的空上下文**。
5.  `TriggerManager` 将这个**空的 `StreamContext`** 连同 `ColdStartInitiationEvent` 事件一同派发出去，以触发通用的问候语。

此双轨制流程无需修改任何核心系统代码，仅通过合理调用现有接口即可实现，保证了方案的稳定性和兼容性。

---

这份经过强化的设计文档详细说明了配置文件的修改方案、新插件的内部架构以及与核心系统的交互模式。请您审阅。如果这份蓝图符合您的预期，我们就可以准备将此计划交付实施。

另外附加：我计划在 InitiationPlanner 中实现一个策略选择系统。每次被 TriggerManager 触发时，它会评估多种“主动聊天策略”的“适宜度分数”，然后选择分数最高的策略来执行。

以下是我初步设计的几种策略：

ColdStartGreetingStrategy (冷启动问候策略)

触发条件：仅在 TriggerManager 派发 ColdStartInitiationEvent 事件时触发。
核心逻辑：生成一句通用的、友好的问候语，比如“你好呀！”或者“最近怎么样？”。这是为了“唤醒”那些很久没聊天的私聊对象。
适宜度分数：固定高分（例如 1.0），确保在冷启动时优先执行。
MemoryDrivenStrategy (记忆驱动策略)

触发条件：常规触发 (ProactiveInitiationEvent)，且当前聊天流的上下文不为空。
核心逻辑：
查询 MemoryManager，获取关于当前聊天对象的长期记忆或近期摘要。
查询 ContextManager，分析最近的几条对话，寻找可以延续的话题。
利用 LLM 生成一个与上下文或记忆相关的话题。例如：“我们上次聊到的那个项目，后来进展如何了？”
适宜度分数计算 (借鉴AFC)：
context_relevance_score (上下文相关性)：上下文越丰富、越接近现在，分数越高。
relationship_score (关系分)：从 RelationshipManager 获取，关系越好，越适合深入聊记忆话题。
final_score = (context_relevance_score * 权重) + (relationship_score * 权重)
TaskDrivenStrategy (任务/日程驱动策略)

触发条件：常规触发。
核心逻辑：
查询 ScheduleManager 或 MonthlyPlanManager，看看今天或最近有没有“待办事项”或“计划”。
如果有，可以围绕这个任务发起对话。例如：“我看到日程表上说今天要去图书馆，准备好了吗？”
适宜度分数计算：
task_urgency_score (任务紧急度)：任务越紧急，分数越高。
task_relevance_score (任务相关度)：如果任务与当前聊天对象有关，分数更高。
final_score = (task_urgency_score * 权重) + (task_relevance_score * 权重)
GenericTopicStrategy (通用话题策略)

触发条件：作为所有其他策略都无法执行时的“兜底”策略。
核心逻辑：从一个预设的话题库（或者让 LLM 随机生成）中挑选一个通用的话题，比如“今天天气不错，适合出门散步呢”或者“最近有什么有趣的新闻吗？”。
适宜度分数：固定低分（例如 0.1），确保它是最后的选择。