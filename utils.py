import logging
import os
from typing import List, Dict
import json

import pandas as pd

# 配置 logging 模块
logging.basicConfig(level=logging.WARNING, format='%(message)s')


# ANSI 转义序列，用于设置文本颜色
class Colors:
    ERROR = "\033[91m"  # 红色
    WARNING = "\033[93m"  # 黄色
    RESET = "\033[0m"  # 重置颜色


# 打印 WARNING 消息
def log_warning(message):
    logging.warning(f"{Colors.WARNING}{message}{Colors.RESET}")


def log_error(message):
    logging.error(f"{Colors.ERROR}{message}{Colors.RESET}")


# # 示例使用
# log_error("这是一个警告消息！")

def paser_list_from_str(string: str = None) -> List[str]:
    """ string 标准格式为 "['a','b','c']" """
    remove_lis = ["\"", "\'", "[", "]", " ", "\n", "`"]
    try:
        substring = "".join([x for x in string if x not in remove_lis])

        if "python" in substring:
            substring = substring.replace("python", "")

        return_lis = substring.split(",")
        return return_lis

    except Exception as e:
        log_error("字符串解析错误！")
        raise e


def parse_json_from_str(string: str = None) -> dict:
    remove_lis = ["\n", "`"]

    try:
        substring = "".join([x for x in string if x not in remove_lis])

        if "json" in substring:
            substring = substring.replace("json", "")

        return_dict = json.loads(substring)
        return return_dict

    except Exception as e:
        # log_error("字符串解析错误！")
        raise e


def parse_df_from_dict(data: Dict[str, Dict]):
    df = pd.DataFrame.from_dict(data, orient='index')

    # 重置索引，使企业类型成为一列
    df.reset_index(inplace=True)
    df.rename(columns={'index': '企业类型'}, inplace=True)
    return df


# lis = paser_list_from_str("['a','b','c']")
# print(lis)

def get_sql_files(directory, suffix: str = ".sql"):
    # 获取指定目录下指定后缀名的所有文件名(不带后缀)
    sql_files = [f.split(".")[0].strip() for f in os.listdir(directory) if f.endswith(suffix)]
    return sql_files


def get_all_directories(directory):
    # 获取指定目录下所有目录名
    return [name for name in os.listdir(directory) if os.path.isdir(os.path.join(directory, name))]


def filter_data_by_db(
        data: pd.DataFrame = None,
        db_lis: List = None
):
    data["DATABASE"] = data["DATABASE"].str.lower()
    db_lis = [db.lower() for db in db_lis]
    # 筛选出指定数据库上的问题
    data = data[data["DATABASE"].isin(db_lis)].reset_index().drop(columns=["index"])

    return data


def filter_errors_lis(data: List, type_lis: List):
    filter_lis = []
    for row in data:
        if row["type"] in type_lis:
            filter_lis.append(row)

    return filter_lis


def count_db_distribution(data: pd.DataFrame, db_percent: float = 1):
    data = data["DATABASE"].value_counts().sort_values(ascending=False)
    data = data.sort_values(ascending=False)
    data = data.to_frame(name='Count').reset_index()

    count = int(len(data) * db_percent) if int(len(data) * db_percent) > 1 else 1

    return data[:count]


def extract_data_from_results(data: List):
    df = pd.DataFrame()

    q_lis, sql_lis, db_lis = [], [], []
    for row in data:
        q_lis.append(row["question"])
        sql_lis.append(row["gold sql"])
        db_lis.append(row["database"])

    df["NLQ"] = q_lis
    df["GOLD SQL"] = sql_lis
    df["DATABASE"] = db_lis

    return df


def remove_data_by_db(data: pd.DataFrame, reserve_rate=0.85):
    db_df = count_db_distribution(data)

    db_lis = list(db_df["DATABASE"])[:int(len(db_df) * reserve_rate)]

    data = data[data["DATABASE"].isin(db_lis)]

    return data


def remove_data(
        all_data: pd.DataFrame,  # 全部数据文件
        results: List,  # 包含删除数据的结果列表
        open_gini: bool = True,  # 按照 gini 系数删除样本，样本集中程度越高则删除比例越大
        min_rate: float = 0.3,
        rate: float = 0.7,  # 删除样本的基础比例，若开启 gini 系数，则此参数失效
        row_type_lis: List = None,
        db_percent: float = 1  # 0-1 范围内的浮点数，表示限定数据库分布范围
):
    """ 从全部数据文件中删除某类型错误数据 """
    if row_type_lis:
        # 根据指定错误类型筛选数据
        results = filter_errors_lis(data=results, type_lis=row_type_lis)

    # 计算每一个数据库的权重
    db_dist = count_db_distribution(all_data, db_percent)
    db_lis = list(db_dist["DATABASE"])
    count_lis = list(db_dist["Count"])

    weight_lis = {}
    for ind, db in enumerate(db_lis):
        if open_gini:
            pre_weight = count_lis[ind] / db_dist["Count"].sum()
            weight_lis[db] = pre_weight if pre_weight > min_rate else min_rate
        else:
            weight_lis[db] = rate  # 有点奇妙，但不难理解

    exclude_question_lis = []

    import random
    for row in results:
        db = row["database"]
        if db in weight_lis.keys():
            rand_num = random.random()
            if rand_num - weight_lis[db] < 0.00001:
                exclude_question_lis.append(row["question"])

    refine_data = all_data[~all_data["NLQ"].isin(exclude_question_lis)]

    return refine_data


def remove_database_data(
        all_data: pd.DataFrame,  # 全部数据文件
        open_gini: bool = True,  # 按照 gini 系数删除样本样本集中程度越高则删除比例越大
        multiplier: float = 1,  # 作为 gini 系数的乘子，扩大命中比例
        rate: float = 0.7,  # 删除样本的基础比例，若开启 gini 系数，则此参数失效
        db_percent: float = 1,  # 0-1 范围内的浮点数，表示限定数据库分布范围
        min_rate: float = 0.1
):
    """ 仅根据数据库分布对错误文件进行删除 """
    question_lis, database_lis = list(all_data["NLQ"]), list(all_data["DATABASE"])

    # 计算每一个数据库的权重
    db_dist = count_db_distribution(all_data, db_percent)
    db_lis = list(db_dist["DATABASE"])
    count_lis = list(db_dist["Count"])

    weight_lis = {}
    for ind, db in enumerate(db_lis):
        if open_gini:
            pre_weight = count_lis[ind] / db_dist["Count"].sum() * multiplier
            weight_lis[db] = pre_weight if pre_weight > min_rate else min_rate
        else:
            weight_lis[db] = rate  # 有点奇妙，但不难理解

    exclude_question_lis = []

    import random
    for ind, question in enumerate(question_lis):
        db = database_lis[ind]
        if db in weight_lis.keys():
            rand_num = random.random()
            if rand_num - weight_lis[db] < 0.00001:
                exclude_question_lis.append(question)

    refine_data = all_data[~all_data["NLQ"].isin(exclude_question_lis)]

    return refine_data


def add_data(
        all_data: pd.DataFrame,
        results: List,
        open_gini: bool = True,  # 按照 gini 系数删除样本，样本集中程度越高则删除比例越大
        rate: float = 0.7,  # 删除样本的基础比例，若开启 gini 系数，则此参数失效
        row_type_lis: List = None,
        db_percent: float = 1  # 0-1 范围内的浮点数，表示限定数据库分布范围
):
    if row_type_lis:
        # 根据指定错误类型筛选数据
        results = filter_errors_lis(data=results, type_lis=row_type_lis)

    # original_db_lis = list(all_data["DATABASE"]
    question_lis = list(all_data["NLQ"])
    # 计算每一个数据库的权重
    db_dist = count_db_distribution(extract_data_from_results(results), db_percent)
    db_lis = list(db_dist["DATABASE"])
    count_lis = list(db_dist["Count"])

    weight_lis = {}
    for ind, db in enumerate(db_lis):
        weight_lis[db] = count_lis[ind] / db_dist["Count"].sum() if open_gini else rate  # 有点奇妙，但不难理解

    add_question_lis = []

    import random
    for row in results:
        db = row["database"]
        question = row["question"]
        if db in weight_lis.keys() and question not in question_lis:
            rand_num = random.random()
            if rand_num - weight_lis[db] < 0.00001:
                add_question_lis.append(row)

    df = extract_data_from_results(add_question_lis)

    df_concatenated = pd.concat([all_data, df], axis=0)

    return df_concatenated


def build_index_again(
        data_source: str = None,
        data: pd.DataFrame = None
):
    db_lis = list(set(list(data["DATABASE"])))

    all_db_source = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\spider\all_database"

    origin_db_lis = get_sql_files(data_source)

    except_db = [db for db in db_lis if db not in origin_db_lis]

    print(len(except_db))

    for db in except_db:
        with open(fr"{all_db_source}\{db}.sql", "r", encoding="utf-8") as file:
            text = file.read()
        with open(fr"{data_source}\{db}.sql", "w", encoding="utf-8") as file:
            file.write(text)


if __name__ == "__main__":
    # dis
    # df_lis = get_sql_files(
    #     r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\spider\hard")
    # print(len(df_lis))
    # df = filter_data_by_db(df, df_lis)
    # dis = count_db_distribution(df)
    # print(dis)
    # dis.to_excel(
    #     r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\bird\distribution.xlsx",
    #     index=False)
    # dirs = get_sql_files(
    #     r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\spider\hard")
    # print(len(dirs))
    #
    # data_dev = pd.read_excel(
    #     r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\dataset\spider\SPIDER_DEV_DATASET.xlsx")
    # data_test = pd.read_excel(
    #     r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\dataset\spider\SPIDER_TEST_DATASET.xlsx")
    # data = pd.concat([data_test, data_dev], axis=0)
    # print(data)
    # dis = count_db_distribution(data)
    # print(len(dis))

    # db_lis = get_sql_files(r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\bird\databases")
    # print(len(db_lis))
    # dirs = get_sql_files(
    #     r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\spider\medium")
    # print(len(dirs))
    # data = pd.read_excel(
    #     r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\benchmark\hard\dataset_v4.xlsx")
    # dis = count_db_distribution(data)
    # db_lis = list(dis["DATABASE"])
    #
    # for db in db_lis:
    #     with open(
    #             rf"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\spider\all_database\{db}.sql",
    #             "r", encoding="utf-8") as file:
    #         text = file.read()
    #     with open(
    #             rf"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\spider\hard\{db}.sql",
    #             "w", encoding="utf-8"
    #     ) as file:
    #         file.write(text)
    with open(
            r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\logs\bird\agent_agent_agent\error_summary_bird_multi_700.json",
            'r', encoding='utf-8') as file:
        data1 = json.load(file)
    # data1 = filter_errors_lis(data1, ["1", "0", "3", "4"])
    # with open(
    #         r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\logs\bird\agent_agent_agent\error_summary_error_2_127.json",
    #         'r', encoding='utf-8') as file:
    #     data2 = json.load(file)
    # data1.extend(data2)
    # with open(
    #         r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\logs\bird\agent_agent_agent\error_summary_bird_multi_700_new.json",
    #         'w', encoding='utf-8') as file:
    #     json.dump(data1, file, ensure_ascii=False, indent=4)
    # data = filter_errors_lis(data, ["1"])
    # data = extract_data_from_results(data)
    # data.to_excel(
    #     r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\logs\spider\norm_none_rsl\error_1.xlsx",
    #     index=False)

    # import random

    # sub_data = random.sample(data, 500)
    # with open(
    #         r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\logs\bird\agent_agent_agent\error2.json",
    #         'w', encoding='utf-8') as file:
    #     json.dump(sub_data, file, ensure_ascii=False, indent=4)
    # print(len(db_lis))
    # # 总共 193 个数据库，问题只有
    # 所有数据库
    # save_path = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\benchmark\hard\new dataset"
    #
    # db_lis = get_sql_files(
    #     r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\spider\hard_orgin")
    #
    # # 问题对应的数据库
    # df = pd.read_excel(
    #     r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\spider\test_database\")
    # q_db_lis = list(set(list(df["DATABASE"])))
    #
    # exclude_db = [db for db in db_lis if db not in q_db_lis]
    #
    # df = pd.read_excel(
    #     r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\benchmark\hard\dataset.xlsx")
    #
    # df = df[df["DATABASE"].isin(exclude_db)].reset_index()
    #
    # df.to_excel(save_path + r"\exclude_question.xlsx", index=False)
