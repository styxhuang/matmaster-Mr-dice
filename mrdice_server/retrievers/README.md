# Retrievers 模块说明

## 作用

`retrievers` 是一个**适配器层**，用于统一不同数据库的调用接口。

### 主要功能

1. **统一接口**：为不同数据库提供统一的 `fetch()` 方法
2. **参数转换**：将统一的 filters 格式转换为每个数据库特定的 API 参数
3. **数据转换**：将数据库返回的原始数据转换为统一的 `SearchResult` 格式
4. **文件保存**：调用数据库的 utils 函数保存结构文件

## 工作流程

```
用户查询
  ↓
预处理 (preprocessor)
  ↓ 生成统一的 filters
数据库选择 (router)
  ↓ 选择数据库列表
并行搜索 (searcher)
  ↓ 调用对应的 Retriever
Retriever.fetch()
  ↓
1. 转换 filters → 数据库特定参数
2. 调用数据库 API/utils 函数
3. 保存结构文件
4. 转换结果 → SearchResult 格式
  ↓
返回统一的 SearchResult 列表
```

## 当前实现

### BohriumPublicRetriever

**功能**：
- 将统一的 filters（formula, elements, space_group, band_gap, energy）转换为 Bohrium API 的 payload
- 调用 Bohrium API 获取数据
- 使用 `save_structures_bohriumcrystal` 保存结构文件
- 将 API 返回的数据转换为 `SearchResult` 格式

**示例**：
```python
retriever = BohriumPublicRetriever()
results = retriever.fetch(
    filters={
        "formula": "Fe2O3",
        "elements": ["Fe", "O"],
        "band_gap": {"min": 0.5, "max": 3.0}
    },
    n_results=10,
    output_format="cif"
)
# 返回: List[SearchResult]
```

## 为什么需要 Retriever？

### 1. 统一接口
不同数据库有不同的 API 和参数格式：
- **Bohrium**: REST API，需要特定的 payload 格式
- **MOFdb SQL**: SQL 查询
- **OpenLAM**: 不同的 API 格式
- **OPTIMADE**: OPTIMADE filter 字符串

Retriever 将这些差异封装起来，提供统一的接口。

### 2. 数据格式转换
每个数据库返回的数据格式不同：
- **Bohrium**: JSON 格式，字段名如 `crystal_ext.band_gap`
- **MOFdb**: SQL 查询结果
- **OPTIMADE**: OPTIMADE 标准格式

Retriever 将这些转换为统一的 `SearchResult` 格式。

### 3. 便于扩展
添加新数据库时，只需：
1. 在 `database/xxx_database/` 下创建 `utils.py` 和 `constant.py`
2. 在 `retrievers/` 下创建对应的 Retriever 类
3. 在 `searcher.py` 中注册

## 与 database/utils.py 的关系

- **utils.py**: 包含数据库的核心函数（API 调用、文件保存等）
- **Retriever**: 调用 utils.py 中的函数，并处理参数转换和数据格式转换

**示例**：
```python
# Retriever 调用 utils 函数
from bohriumpublic_database.utils import (
    save_structures_bohriumcrystal,
    normalize_formula,
    ...
)

# Retriever 负责：
# 1. 转换 filters → API 参数
# 2. 调用 API（或使用 utils 函数）
# 3. 调用 save_structures_bohriumcrystal 保存文件
# 4. 转换结果 → SearchResult
```

## 待实现的 Retriever

目前只有 `BohriumPublicRetriever` 已实现，其他数据库的 Retriever 待实现：

- [ ] `MofdbSqlRetriever` - 用于 MOFdb SQL 数据库
- [ ] `OpenlamRetriever` - 用于 OpenLAM 数据库
- [ ] `OptimadeRetriever` - 用于 OPTIMADE 数据库

## 总结

**Retriever = 适配器 + 转换器**

- **适配器**：统一不同数据库的调用接口
- **转换器**：统一参数格式和数据格式

这样，上层的 `searcher` 和 `server` 不需要关心每个数据库的具体实现细节，只需要调用统一的 `fetch()` 方法即可。

