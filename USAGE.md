# MrDice 服务器使用指南

## 启动服务器

### 方式 1: 使用 uv 运行（推荐）

```bash
# 在项目根目录下运行
uv run python -m mrdice_server.server

# 指定端口和主机
uv run python -m mrdice_server.server --port 50001 --host 0.0.0.0

# 指定日志级别
uv run python -m mrdice_server.server --log-level DEBUG
```

### 方式 2: 激活虚拟环境后运行

```bash
# 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows

# 运行服务器
python -m mrdice_server.server
```

### 命令行参数

- `--port`: 服务器端口（默认: 50001）
- `--host`: 服务器主机（默认: 0.0.0.0）
- `--log-level`: 日志级别，可选值: DEBUG, INFO, WARNING, ERROR（默认: INFO）

## 服务器信息

- **传输协议**: MCP Streamable HTTP (`streamable-http`)
- **默认端口**: 50001
- **默认主机**: 0.0.0.0（监听所有网络接口）
- **MCP 端点**: `http://<host>:<port>/mcp`

## Token 鉴权（可选）

默认情况下服务端不鉴权。如果你想为 MCP 端点加一层简单的 token 鉴权（适合 UAT/内网），设置环境变量：

- `MR_DICE_MCP_TOKEN=<your_token>`

启用后：

- **访问方式 1（URL 参数）**：`/mcp?token=<your_token>`
- **访问方式 2（Header）**：`Authorization: Bearer <your_token>`

示例：

`https://structure-generator-uat-2-uuid1767842266.appspace.uat.bohrium.com/mcp?token=YOUR_TOKEN`

## 可用的工具

### fetch_structures_from_db

统一的材料数据库搜索工具，支持自然语言查询。

**参数**:
- `query` (str, 必需): 搜索查询，支持自然语言
- `n_results` (int, 可选): 返回结果数量（默认: 5，最大: 20）
- `output_format` (str, 可选): 输出格式，可选值: "cif", "json"（默认: "cif"）

**示例查询**:
- "找一些 Fe2O3 材料"
- "搜索带隙大于 2.0 eV 的半导体材料"
- "查找包含 Li 和 O 的电池材料"
- "MOF 材料，比表面积大于 1000 m²/g"

## 使用方式

### 1. 通过 MCP 客户端连接

MrDice 服务器使用 MCP (Model Context Protocol) 协议，可以通过支持 MCP 的客户端连接：

#### 使用 Claude Desktop 或其他 MCP 客户端

在 MCP 客户端配置中添加：

```json
{
  "mrdice": {
    "command": "uv",
    "args": [
      "run",
      "python",
      "-m",
      "mrdice_server.server"
    ],
    "transport": "streamable-http"
  }
}
```

### 2. 通过 HTTP（Streamable）直接访问

服务器启动后，可以通过 MCP Streamable HTTP 端点访问（FastMCP 默认路径是 `/mcp`）：

```
http://localhost:50001/mcp
```

### 3. 测试工具调用

可以使用 Python 脚本测试：

```python
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from mrdice_server.core.server import fetch_structures_from_db

async def test_search():
    result = await fetch_structures_from_db(
        query="找一些 Fe2O3 材料",
        n_results=3,
        output_format="cif"
    )
    print(f"找到 {result['n_found']} 个结果")
    print(f"返回 {result['returned']} 个结果")
    for i, r in enumerate(result['results'][:3], 1):
        print(f"{i}. {r.get('formula', 'N/A')} - {r.get('name', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(test_search())
```

### 4. 使用 curl 测试连接（Streamable HTTP）

```bash
# 说明：Streamable HTTP 通常需要 MCP 客户端按协议发起请求；
# 这里仅用于确认端口可连通
curl -I http://localhost:50001
```

## 工作流程

服务器执行以下流程：

1. **预处理**:
   - 意图识别：识别材料类型（crystal/mof/unknown）和领域
   - 参数构建：从自然语言查询中提取搜索参数
   - 参数矫正：如果参数无效，自动矫正

2. **数据库选择**:
   - 根据材料类型、领域和过滤器智能选择数据库
   - 支持的数据库：bohriumpublic, mofdb, mofdbsql, openlam, optimade

3. **并行搜索**:
   - 在选定的数据库中并行执行搜索
   - 支持降级策略：如果严格搜索无结果，逐步放宽条件

4. **后处理**:
   - 结果排序和去重
   - 错误处理和重试
   - 结果格式化

## 环境变量配置

确保 `.env` 文件中配置了必要的环境变量：

```bash
# LLM 配置（用于意图识别和参数构建）
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek/deepseek-chat
LLM_API_BASE=https://api.deepseek.com/v1
LLM_API_KEY=your_api_key_here

# 数据库配置
DB_CORE_HOST=your_db_host
BOHRIUM_CORE_HOST=https://bohrium-core.dp.tech
BOHRIUM_X_USER_ID=your_user_id

# 数据目录
MR_DICE_DATA_DIR=/path/to/data
```

## 故障排查

### 服务器无法启动

1. 检查 Python 版本：需要 Python >= 3.12
   ```bash
   python --version
   ```

2. 检查依赖是否安装：
   ```bash
   uv sync
   ```

3. 检查端口是否被占用：
   ```bash
   lsof -i :50001  # macOS/Linux
   netstat -ano | findstr :50001  # Windows
   ```

### LLM 调用失败

1. 检查 `.env` 文件中的 `LLM_API_KEY` 是否正确
2. 运行测试脚本验证 LLM 连接：
   ```bash
   python tests/test_llm_simple.py
   ```

### 数据库连接失败

1. 检查数据库相关的环境变量是否配置
2. 检查网络连接和数据库服务是否可用

## 日志

服务器日志会输出到控制台，可以通过 `--log-level` 参数调整日志级别：

- `DEBUG`: 详细调试信息
- `INFO`: 一般信息（默认）
- `WARNING`: 警告信息
- `ERROR`: 错误信息

## 更多信息

查看 `README.md` 获取更多项目信息。

