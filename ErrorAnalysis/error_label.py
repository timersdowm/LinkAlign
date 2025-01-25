import json
from typing import List

from SchemaLinkingCompare.config import *
from SchemaLinkingCompare.llms.zhipu.ZhipuModel import ZhipuModel
from SchemaLinkingCompare.pipes.RagPipeline import RagPipeLines
from SchemaLinkingCompare.tools.SchemaLinkingTool import SchemaLinkingTool

"""
1、总结四种错误类型的数量分布，如何判断每一种错误应该属于哪一种错误类型，为每一个错误打标签
2、编写新框架下的实验代码
3、依然使用现有的错误样本进行测试
4、构造MPP数据库、图数据库、空间数据库大规模 schema 的数据
"""
DATABASE_FOLDER = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\all_database_with_comments"
PREDICT_SUMMARY_PATH = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\预实验\错误分析"
ERROR_SOURCE_FILE = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\预实验\错误分析"


# 判定规则
# 1、若不存在 predict schemas 中出现的数据表和 gold schema 中重合，则标记为 “1”
# 2、若 predict schemas 和 gold schema 存在数据库重合，则获取对应数据库建表字符串，判断不重合的表是否在字符串中，若不在，则标记为“2”，若全部都在，则标记为”3“
# 3、若 predict schemas 和 gold schemas 完全相同，但字段存在不同，则标记为“4”
# 4、若以上情况均不满足，则标记为 “0”

def cal_metric(gold_columns: List, predict_columns: List):
    # 计算精准率
    num = len(predict_columns)
    count = 0
    for col in predict_columns:
        if col in gold_columns:
            count += 1
    precision = count / num if num > 0 else 0

    # 计算召回率
    num = len(gold_columns)
    count = 0
    for col in gold_columns:
        if col in predict_columns:
            count += 1
    recall = count / num if num > 0 else 0

    # 计算 F1-Score
    f1_score = 2 * recall * precision / (precision + recall) if (precision + recall) > 0 else 0

    return precision, recall, f1_score


def remove_symbols(string: str) -> str:
    symbol_lis = ["'", '"', "`"]

    for symbol in symbol_lis:
        string = string.replace(symbol, "")

    return string


def parse_tables_from_str(schema: str):
    substring = schema[schema.rfind("[") + 1:schema.rfind("]")]
    tables = [x.strip().lower() for x in remove_symbols(substring).split(",")]
    tables = [".".join(col.split(".")[-2:]) for col in tables]
    tables = [col.split(".")[0].strip() for col in tables]

    # 去重
    tables = list(set(tables))

    return tables


def parse_columns_from_str(schema: str):
    substring = schema[schema.rfind("[") + 1:schema.rfind("]")]
    columns = [x.strip().lower() for x in remove_symbols(substring).split(",")]

    columns = [remove_symbols(x) for x in columns]
    # 去重
    columns = list(set(columns))

    columns = [".".join(col.split(".")[-2:]) for col in columns]

    return columns


def get_database_str(database: str):
    with open(DATABASE_FOLDER + rf"\{database}.sql", "r", encoding="utf-8") as file:
        result = file.read().strip().lower()

    return result


def get_data_label(gold_schema: str, predict_schema: str, database: str = None, prompt: str = None):
    gold_tables = parse_tables_from_str(gold_schema)
    predict_tables = parse_tables_from_str(predict_schema)

    database_str = get_database_str(database)
    # 判断是否为第一类错误
    # 需要判断gold schema 是否出现在检索到的文本块中

    if database.lower() not in prompt.lower():
        return "1"

    # 判断是否为第二类错误
    for t in predict_tables:
        if t not in gold_tables:
            if t not in database_str:
                return "2"
            else:
                return "3"  # 2 可能被错误当做3
    for t in gold_tables:
        if t not in predict_tables:
            return "3"

    gold_columns = parse_columns_from_str(gold_schema)
    predict_columns = parse_columns_from_str(predict_schema)

    # 可能的特殊情况，
    if len(gold_columns) == 1 and gold_columns[0].split(".")[1] == "*":
        return 0

    for c in predict_columns:
        if c not in gold_columns:
            return "4"

    for c in gold_columns:
        if c not in predict_columns:
            return "4"

    return "0"


def add_error_label_llama(data: List):
    """ 为数据列表中的每个元素添加标签 """
    llm = ZhipuModel(is_call=False)
    index = RagPipeLines.build_index_from_source(
        data_source=ALL_DATABASE_DATA_SOURCE,
        persist_dir=PERSIST_DIR,
        is_vector_store_exist=True,
        index_method="VectorStoreIndex"
    )

    data_lis = []
    for row in data:
        try:
            prompt = SchemaLinkingTool.link_schema_by_question(llm=llm, index=index, question=row["question"]).lower()
            label = get_data_label(row["gold schema"], row["llama_schema"], row["database"], prompt=prompt)
            row["type"] = label
            data_lis.append(row)
        except Exception as e:
            print(e)

    return data_lis


def add_error_label_precise(data: List):
    """ 为数据列表中的每个元素添加标签 """
    # 必须包含 database、predict_database、is_A、gold_schema 和 llama_schema'
    results = []
    for row in data:
        try:
            assert row["gold schema"] != "[]"
            assert "[" in row["llama_schema"] and "]" in row["llama_schema"]
            gold_tables = parse_tables_from_str(row["gold schema"])
            predict_tables = parse_tables_from_str(row["llama_schema"])

            gold_columns = parse_columns_from_str(row["gold schema"])
            predict_columns = parse_columns_from_str(row["llama_schema"])

            # 计算精准率和召回率
            precision, recall, f1_score = cal_metric(gold_columns, predict_columns)
            row["precision"] = precision
            row["recall"] = recall
            row["f1_score"] = f1_score

            if not row["is_A"]:
                row["type"] = "1"
                results.append(row)
                continue

            if row["predict_database"].lower() != row["database"].lower():
                row["type"] = "2"
                results.append(row)
                continue

            is_C = False

            # 判断是否为第三类错误
            for t in predict_tables:
                if t not in gold_tables:
                    row["type"] = "3"
                    is_C = True
                    break
            if is_C:
                results.append(row)
                continue

            for t in gold_tables:
                if t not in predict_tables:
                    row["type"] = "3"
                    is_C = True
                    break
            if is_C:
                results.append(row)
                continue

            # 可能的特殊情况，
            if len(gold_columns) == 1 and gold_columns[0].split(".")[1] == "*":
                row["type"] = "0"
                results.append(row)
                continue

            is_D = False

            for c in predict_columns:
                if c not in gold_columns:
                    row["type"] = "4"
                    is_D = True
                    break
            if is_D:
                results.append(row)
                continue

            for c in gold_columns:
                if c not in predict_columns:
                    row["type"] = "4"
                    is_D = True
                    break
            if is_D:
                results.append(row)
                continue

            row["type"] = "0"
            results.append(row)
        except Exception as e:
            # print(e)
            print(row["question"])
            continue

    return results


def error_count_statistics(
        data: List = None,
        save_path: str = None,
):
    if not data:
        error_path = save_path + r"\error_summary.json"
        with open(error_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

    count = len(data)

    correct_count = 0

    A_error_count = 0
    B_error_count = 0
    C_error_count = 0
    D_error_count = 0

    num = 0
    precision = 0
    recall = 0
    f1_score = 0

    for row in data:
        type = row["type"]
        num += 1
        if type == "0":
            correct_count += 1
            precision += 1
            recall += 1
            f1_score += 1
        else:
            precision += row["precision"]
            recall += row["recall"]
            f1_score += row["f1_score"]

            if type == "1":
                A_error_count += 1
            elif type == "2":
                B_error_count += 1
            elif type == "3":
                C_error_count += 1
            elif type == "4":
                D_error_count += 1

    print("# LlamaIndex 方法实现 schema linking 结果：")
    print(f"# 样本总数：{count}")
    print(f"# 正确预测样本数量：{correct_count} ,占比：{correct_count / count}")
    print(
        f"# 错误(1)样本数量：{A_error_count} ,占错误样本比例：{A_error_count / (count - correct_count) if count - correct_count > 0 else 0}，总样本比例：{A_error_count / count}")
    print(
        f"# 错误(2)样本数量：{B_error_count} ,占错误样本比例：{B_error_count / (count - correct_count) if count - correct_count > 0 else 0}，总样本比例：{B_error_count / count}")
    print(
        f"# 错误(3)样本数量：{C_error_count} ,占错误样本比例：{C_error_count / (count - correct_count) if count - correct_count > 0 else 0}，总样本比例：{C_error_count / count}")
    print(
        f"# 错误(4)样本数量：{D_error_count} ,占错误样本比例：{D_error_count / (count - correct_count) if count - correct_count > 0 else 0}，总样本比例：{D_error_count / count}")
    print("### ")
    print(
        f"Precision：{precision / num}")
    print(
        f"Recall：{recall / num}")
    print(
        f"f1_score：{f1_score / num}")


def error_evaluate_run(
        data: List = None,
        mode="precise",  # 模式 llama：通过 llama_index 进行 schema_linking ，precise 则通过 pipeline 或者 agent 方式添加,
        save_path: str = None,
        verbose: bool = True,
        suffix: str = ""
):
    if not data:
        with open(
                ERROR_SOURCE_FILE + r"\all_db_few_shot_difficult_311_tr.json",
                'r', encoding='utf-8') as file:
            data = json.load(file)

    data = add_error_label_llama(data) if mode == "llama" else add_error_label_precise(data)
    # print(data)
    save_path = save_path if save_path else ERROR_SOURCE_FILE

    with open(save_path + rf'\error_summary_{suffix}.json', 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

    if verbose:
        error_count_statistics(data)

    return data
    # random.shuffle(data)
    # save_data = data[:int(len(data) * 0.3)]
    # with open(save_path + r'\error_sample.json', 'w', encoding='utf-8') as file:
    #     json.dump(save_data, file, ensure_ascii=False, indent=4)


def save_error_sample():
    ERROR_SUMMARY_FILE = ERROR_SOURCE_FILE + r"\error_summary.json"
    with open(ERROR_SUMMARY_FILE, 'r', encoding='utf-8') as file:
        data = json.load(file)

    A_lis = []
    B_lis = []
    C_lis = []
    D_lis = []

    all_error_lis = []

    for row in data:
        type = row["type"]
        all_error_lis.append(row)
        if type == "1":
            A_lis.append(row)
        elif type == "2":
            B_lis.append(row)
        elif type == "3":
            C_lis.append(row)
        elif type == "4":
            D_lis.append(row)

    with open(
            rf"{ERROR_SOURCE_FILE}\errors\error_A.json",
            'w', encoding="utf-8") as json_file:
        json.dump(A_lis, json_file, indent=4)
    with open(
            rf"{ERROR_SOURCE_FILE}\errors\error_B.json",
            'w', encoding="utf-8") as json_file:
        json.dump(B_lis, json_file, indent=4)
    with open(
            rf"{ERROR_SOURCE_FILE}\errors\error_C.json",
            'w', encoding="utf-8") as json_file:
        json.dump(C_lis, json_file, indent=4)
    with open(
            rf"{ERROR_SOURCE_FILE}\errors\error_D.json",
            'w', encoding="utf-8") as json_file:
        json.dump(D_lis, json_file, indent=4)

    with open(
            rf"{ERROR_SOURCE_FILE}\errors\error_all.json",
            'w', encoding="utf-8") as json_file:
        json.dump(all_error_lis, json_file, indent=4)


def error_database_count():
    ERROR_SUMMARY_FILE = ERROR_SOURCE_FILE + r"\errors\error_A.json"
    with open(ERROR_SUMMARY_FILE, 'r', encoding='utf-8') as file:
        data = json.load(file)

    databases = []
    for row in data:
        databases.append(row["database"])

    databases = list(set(databases))
    print(databases)
    print(len(databases))


if __name__ == "__main__":
    # with open(
    #         r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\logs\pipeline_agent_pipeline\error_summary_hard_agent_2_1309.json",
    #         'r', encoding='utf-8') as file:
    #     data = json.load(file)
    #
    # error_count_statistics(data)
    schema = "Based on the discussion and the user query, the necessary schema elements are:\n\n- From `cards` table: `id`, `name`, `artist`, `isPromo`, `uuid`\n- From `rulings` table: `uuid`, a hypothetical `card_uuid` to link to `cards.uuid`\n\nThe `cards.uuid` and `rulings.uuid` will be used to join the tables, and we'll group by `cards.id` to count the rulings. We need to filter for `isPromo = 1` to check for promotional printings. A subquery or window function will be used to find the card with the most rulings."
    table = parse_tables_from_str(schema)
    print(table)