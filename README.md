# Mr. Dice
Mr. Dice — Materials Retriever for Database-Integrated Cross-domain Exploration

## 项目设置

### 使用 UV 管理依赖

本项目使用 [uv](https://github.com/astral-sh/uv) 作为包管理工具。

#### 快速开始

```bash
# 运行初始化脚本（自动安装 uv 并同步依赖）
./uv_setup.sh

# 或手动初始化
uv sync
```

#### 安装 UV

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pip
pip install uv
```

#### 初始化项目

```bash
# 同步依赖（会自动创建虚拟环境）
uv sync

# 或安装开发依赖
uv sync --group dev
```

**注意**: 如果项目依赖 `dp.agent`（内部包），可能需要单独安装：
```bash
pip install bohr-agent-sdk
# 或根据实际情况安装
```

#### 运行项目

```bash
# 使用 uv 运行主服务器
uv run python -m mrdice_server.server

# 或激活虚拟环境后直接运行
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows
```

#### 添加依赖

```bash
# 添加生产依赖
uv add package-name

# 添加开发依赖
uv add --dev package-name

# 移除依赖
uv remove package-name
```

#### 更新依赖

```bash
# 更新所有依赖
uv sync --upgrade

# 更新特定包
uv add package-name@latest
```

### 环境变量配置

复制 `.env.example` 文件为 `.env` 并设置以下变量：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# LLM 配置
LLM_PROVIDER=deepseek  # 或 openai
LLM_MODEL=deepseek/deepseek-chat
LLM_API_KEY=your_api_key_here
LLM_API_BASE=  # 可选，自定义 API base URL

# 调试模式
LLM_DEBUG=0  # 设置为 1 启用 LLM 调试日志

# 数据目录配置
# 基础数据目录（可选，默认为项目根目录）
MR_DICE_DATA_DIR=

# Bohrium 输出目录（可选，默认为相对路径）
# macOS 示例: /Users/your_username/Mr-Dice/bohriumpublic_database/Bohriumpublic_Server/materials_data_bohriumpublic
# Linux 示例: /home/Mr-Dice/bohriumpublic_database/Bohriumpublic_Server/materials_data_bohriumpublic
MR_DICE_BOHRIUM_OUTPUT_DIR=
```

**重要**: 如果使用 macOS 或 Windows，需要设置 `MR_DICE_BOHRIUM_OUTPUT_DIR` 为绝对路径，因为默认路径 `/home/Mr-Dice` 在这些系统上不存在。

### 项目结构

```
mrdice_server/
├── server.py          # 主入口点（向后兼容）
├── core/              # 核心模块
│   ├── server.py      # MCP 服务器实现
│   ├── config.py      # 配置管理
│   ├── llm_client.py  # LLM 客户端
│   ├── preprocessor.py # 预处理：意图识别、参数拼接、参数矫正
│   ├── postprocessor.py # 后处理：错误分类、降级策略
│   ├── logger.py      # 日志管理
│   └── error.py       # 报错管理
├── search/            # 搜索相关
│   ├── searcher.py    # 并行数据库搜索
│   ├── router.py      # 路由规划和数据库选择
│   └── ranker.py      # 结果排序
├── models/            # 数据模型
│   └── schema.py      # 数据模型定义
├── retrievers/        # 检索器实现
│   ├── base.py        # 检索器基类
│   └── bohriumpublic.py # Bohrium 检索器
└── database/          # 数据库实现
    ├── bohriumpublic_database/
    ├── mofdbsql_database/
    ├── openlam_database/
    └── optimade_database/

tests/                  # 测试文件
├── test_llm_simple.py # LLM 测试脚本
├── test_llm.py        # LLM 测试（完整版）
├── test_mrdice_example.py # 示例测试脚本
└── test.json          # 测试用例配置
```

### 开发

```bash
# 运行测试
uv run pytest

# 代码格式化
uv run black mrdice_server/

# 代码检查
uv run ruff check mrdice_server/

# 类型检查
uv run mypy mrdice_server/
```
