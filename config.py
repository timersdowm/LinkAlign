# -*- coding: utf-8 -*-
# 本地文件存储目录
# ALL_DATABASE_DATA_SOURCE = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\spider\medium"
# ALL_DATABASE_DATA_SOURCE = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\all_database_with_comments"
# ALL_DATABASE_DATA_SOURCE = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\databases"
ALL_DATABASE_DATA_SOURCE = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\bird\databases"
# ALL_DATABASE_DATA_SOURCE = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\spider\all_database"
# ALL_DATABASE_DATA_SOURCE = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\spider\hard_orgin"
# ALL_DATABASE_DATA_SOURCE = r"F:\benchmark\SPIDER2\spider2-lite\extract\databases"

# 训练数据存储目录
DATASET_PATH = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\dataset"

# 索引保存目录
PERSIST_DIR = ALL_DATABASE_DATA_SOURCE + r"\vector_store"

# 日志目录
LOG_DIR = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\logs\bird"
# LOG_DIR = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\logs\spider2"
# LOG_DIR = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\logs\spider"

# SummaryIndex 索引文件存储目录
ALL_DATABASE_SUMMARY_PERSIST_DIR = ALL_DATABASE_DATA_SOURCE + r"\vector_store\SummaryIndex"

# VectorStoreIndex 索引文件存储目录
ALL_DATABASE_VECTOR_PERSIST_DIR = ALL_DATABASE_DATA_SOURCE + r"\vector_store\VectorStoreIndex"

# 本地索引文件存储目录
VECTOR_STORE_PERSIST_DIR = r"E:\documents_for_llms\data03\vector_store"

# 文件存储目录索引是否存在。注意：更新文件目录后第一次使用需要设置为 False
IS_VECTOR_STORE_EXIST = True

# 嵌入模型名称
EMBED_MODEL_NAME = None

# 底层大模型名称
LLM_NAME = "zhipu"

# 过程可视化
VERBOSE = False

# 智普API key
# ZHIPU_API_KEY = "Input yours in this place."

# 模型名称
ZHIPU_MODEL_NAME = "glm-4-air"  # 测试哪种模型效果更好
# ZHIPU_MODEL_NAME = "glm-4-plus"  # 测试哪种模型效果更好


# 两个模型的公共参数
TEMPERATURE = 0.42

MAX_OUTPUT_TOKENS = 4096

CONTEXT_WINDOW = 120000
