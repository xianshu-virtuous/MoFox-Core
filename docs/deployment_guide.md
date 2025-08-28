# MoFox_Bot 部署指南

欢迎使用 MoFox_Bot！本指南将引导您完成在 Windows 环境下部署 MoFox_Bot 的全部过程。

## 1. 系统要求

- **操作系统**: Windows 10 或 Windows 11
- **Python**: 版本 >= 3.10
- **Git**: 用于克隆项目仓库
- **uv**: 推荐的 Python 包管理器 (版本 >= 0.1.0)

## 2. 部署步骤

### 第一步：获取必要的文件

首先，创建一个用于存放 MoFox_Bot 相关文件的文件夹，并通过 `git` 克隆 MoFox_Bot 主程序和 Napcat 适配器。

```shell
mkdir MoFox_Bot_Deployment
cd MoFox_Bot_Deployment
git clone hhttps://github.com/MoFox-Studio/MoFox_Bot.git
git clone https://github.com/MoFox-Studio/Napcat-Adapter.git
```

### 第二步：环境配置

我们推荐使用 `uv` 来管理 Python 环境和依赖，因为它提供了更快的安装速度和更好的依赖管理体验。

**安装 uv:**

```shell
pip install uv
```

### 第三步：依赖安装

**1. 安装 MoFox_Bot 依赖:**

进入 `mmc` 文件夹，创建虚拟环境并安装依赖。

```shell
cd mmc
uv venv
uv pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple --upgrade
```

**2. 安装 Napcat-Adapter 依赖:**

回到上一级目录，进入 `Napcat-Adapter` 文件夹，创建虚拟环境并安装依赖。

```shell
cd ..
cd Napcat-Adapter
uv venv
uv pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple --upgrade
```

### 第四步：配置 MoFox_Bot 和 Adapter

**1. MoFox_Bot 配置:**

- 在 `mmc` 文件夹中，将 `template/bot_config_template.toml` 复制到 `config/bot_config.toml`。
- 将 `template/model_config_template.toml` 复制到 `config/model_config.toml`。
- 根据 [模型配置指南](guides/model_configuration_guide.md) 和 `bot_config.toml` 文件中的注释，填写您的 API Key 和其他相关配置。

**2. Napcat-Adapter 配置:**

- 在 `Napcat-Adapter` 文件夹中，将 `template/template_config.toml` 复制到根目录并改名为 `config.toml`。
- 打开 `config.toml` 文件，配置 `[Napcat_Server]` 和 `[MaiBot_Server]` 字段。
  - `[Napcat_Server]` 的 `port` 应与 Napcat 设置的反向代理 URL 中的端口相同。
  - `[MaiBot_Server]` 的 `port` 应与 MoFox_Bot 的 `bot_config.toml` 中设置的端口相同。

### 第五步：运行

**1. 启动 Napcat:**

请参考 [NapCatQQ 文档](https://napcat-qq.github.io/) 进行部署和启动。

**2. 启动 MoFox_Bot:**

进入 `mmc` 文件夹，使用 `uv` 运行。

```shell
cd mmc
uv run python bot.py
```

**3. 启动 Napcat-Adapter:**

打开一个新的终端窗口，进入 `Napcat-Adapter` 文件夹，使用 `uv` 运行。

```shell
cd Napcat-Adapter
uv run python main.py
```

至此，MoFox_Bot 已成功部署并运行。

## 3. 详细配置说明

### `bot_config.toml`

这是 MoFox_Bot 的主配置文件，包含了机器人昵称、主人QQ、命令前缀、数据库设置等。请根据文件内的注释进行详细配置。

### `model_config.toml`

此文件用于配置 AI 模型和 API 服务提供商。详细配置方法请参考 [模型配置指南](guides/model_configuration_guide.md)。

### 插件配置

每个插件都有独立的配置文件，位于 `mmc/config/plugins/` 目录下。插件的配置由其 `config_schema` 自动生成。详细信息请参考 [插件配置完整指南](plugins/configuration-guide.md)。

## 4. 故障排除

- **依赖安装失败**:
  - 尝试更换 PyPI 镜像源。
  - 检查网络连接。
- **API 调用失败**:
  - 检查 `model_config.toml` 中的 API Key 和 `base_url` 是否正确。
- **无法连接到 Napcat**:
  - 检查 Napcat 是否正常运行。
  - 确认 `Napcat-Adapter` 的 `config.toml` 中 `[Napcat_Server]` 的 `port` 是否与 Napcat 设置的端口一致。

如果遇到其他问题，请查看 `logs/` 目录下的日志文件以获取详细的错误信息。