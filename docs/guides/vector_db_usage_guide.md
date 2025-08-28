# 统一向量数据库服务使用指南

本文档旨在说明如何在 `mmc` 项目中使用新集成的统一向量数据库服务。该服务提供了一个标准化的接口，用于与底层向量数据库（当前为 ChromaDB）进行交互，同时确保了代码的解耦和未来的可扩展性。

## 核心设计理念

1.  **统一入口**: 所有对向量数据库的操作都应通过全局单例 `vector_db_service` 进行。
2.  **抽象接口**: 服务遵循 `VectorDBBase` 抽象基类定义的接口，未来可以轻松替换为其他向量数据库（如 Milvus, FAISS）而无需修改业务代码。
3.  **单例模式**: 整个应用程序共享一个数据库客户端实例，避免了资源浪费和管理混乱。
4.  **数据隔离**: 使用不同的 `collection` 名称来隔离不同业务模块（如语义缓存、瞬时记忆）的数据。在 `collection` 内部，使用 `metadata` 字段（如 `chat_id`）来隔离不同用户或会话的数据。

## 如何使用

### 1. 导入服务

在任何需要使用向量数据库的文件中，只需导入全局服务实例：

```python
from src.common.vector_db import vector_db_service
```

### 2. 主要操作

`vector_db_service` 对象提供了所有你需要的方法，这些方法都定义在 `VectorDBBase` 中。

#### a. 获取或创建集合 (Collection)

在操作数据之前，你需要先指定一个集合。如果集合不存在，它将被自动创建。

```python
# 为语义缓存创建一个集合
vector_db_service.get_or_create_collection(name="semantic_cache")

# 为瞬时记忆创建一个集合
vector_db_service.get_or_create_collection(
    name="instant_memory",
    metadata={"hnsw:space": "cosine"}  # 可以传入特定于实现的参数
)
```

#### b. 添加数据

使用 `add` 方法向指定集合中添加向量、文档和元数据。

```python
collection_name = "instant_memory"
chat_id = "user_123"
message_id = "msg_abc"
embedding_vector = [0.1, 0.2, 0.3, ...]  # 你的 embedding 向量
content = "你好，这是一个测试消息"

vector_db_service.add(
    collection_name=collection_name,
    embeddings=[embedding_vector],
    documents=[content],
    metadatas=[{
        "chat_id": chat_id,
        "timestamp": 1678886400.0,
        "sender": "user"
    }],
    ids=[message_id]
)
```

#### c. 查询数据

使用 `query` 方法来查找相似的向量。你可以使用 `where` 子句来过滤元数据。

```python
query_vector = [0.11, 0.22, 0.33, ...]  # 用于查询的向量
collection_name = "instant_memory"
chat_id_to_query = "user_123"

results = vector_db_service.query(
    collection_name=collection_name,
    query_embeddings=[query_vector],
    n_results=5,  # 返回最相似的5个结果
    where={"chat_id": chat_id_to_query}  # **重要**: 使用 where 来隔离不同聊天的数据
)

# results 的结构:
# {
#     'ids': [['msg_abc']],
#     'distances': [[0.0123]],
#     'metadatas': [[{'chat_id': 'user_123', ...}]],
#     'embeddings': None,
#     'documents': [['你好，这是一个测试消息']]
# }
print(results)
```

#### d. 删除数据

你可以根据 `id` 或 `where` 条件来删除数据。

```python
# 根据 ID 删除
vector_db_service.delete(
    collection_name="instant_memory",
    ids=["msg_abc"]
)

# 根据 where 条件删除 (例如，删除某个用户的所有记忆)
vector_db_service.delete(
    collection_name="instant_memory",
    where={"chat_id": "user_123"}
)
```

#### e. 获取集合数量

使用 `count` 方法获取一个集合中的条目总数。

```python
count = vector_db_service.count(collection_name="semantic_cache")
print(f"语义缓存集合中有 {count} 条数据。")
```
**注意**: `count` 方法目前返回整个集合的条目数，不会根据 `where` 条件进行过滤。

### 3. 代码位置

-   **抽象基类**: [`mmc/src/common/vector_db/base.py`](mmc/src/common/vector_db/base.py)
-   **ChromaDB 实现**: [`mmc/src/common/vector_db/chromadb_impl.py`](mmc/src/common/vector_db/chromadb_impl.py)
-   **服务入口**: [`mmc/src/common/vector_db/__init__.py`](mmc/src/common/vector_db/__init__.py)

---

这份完整的文档应该能帮助您和团队的其他成员正确地使用新的向量数据库服务。如果您有任何其他问题，请随时提出。