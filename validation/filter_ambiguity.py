import json
import os
import pandas as pd
from typing import List, Union, Dict

from llama_index.core.indices.vector_store import VectorIndexRetriever

from SchemaLinkingCompare.config import *
from SchemaLinkingCompare.llms.zhipu.ZhipuModel import ZhipuModel
from SchemaLinkingCompare.pipes.RagPipeline import RagPipeLines
from SchemaLinkingCompare.tools.SchemaLinkingTool import SchemaLinkingTool, get_all_schemas_from_schema_text
from SchemaLinkingCompare.utils import get_sql_files
from SchemaLinkingCompare.prompts.ValidatePromptsStore import *
from SchemaLinkingCompare.prompts.PropmtsStore import *
from SchemaLinkingCompare.ErrorAnalysis.error_label import error_evaluate_run
from SchemaLinkingCompare.preprocess.DataProcess import DataProcess
from SchemaLinkingCompare.utils import filter_data_by_db


class Validate:
    """
    一个通用的校验类。
    用于校验给定样本在不同模式下进行 schema linking 的正确率，以及出现四种错误的比例。
    """
    llm = ZhipuModel()
    turn_n = 2  # 默认不支持参数修改

    @classmethod
    def validate(
            cls,
            llm=None,
            data: pd.DataFrame = None,
            retriever_lis: List[VectorIndexRetriever] = None,  # 外部指定检索数据源
            retrieval_mode: str = "pipeline",
            # none(all info),norm(llama_index retrieve),pipeline(reason enhance),agent(multi-agent)
            locate_mode: str = "pipeline",  # none(all info,llama_index),pipeline(locate),agent(multi-agent debate)
            generate_mode: str = "pipeline",  # none(single prompt),agent(multi-agent debate)
            remove_duplicate: bool = True,  # 不放回检索
            log_save_path: str = None,  # 日志保存路径
            suffix: str = None,  # 用于区分日志文件的后缀
            count: int = None,  # 指定测试数据数量
            is_evaluate: bool = True  # 对结果进行统计
    ):
        count = len(data) if not count else count

        data = (data
                .sample(count)
                .reset_index()
                .drop(columns=["index"])
                )
        question_lis, gold_sql_lis, database_lis = list(data["NLQ"]), list(data["GOLD SQL"]), list(data["DATABASE"])

        llm = llm if llm else cls.llm

        results, error_info = [], []
        for i in range(count):
            try:
                databases, database, predict_schema = cls.validate_schema_linking(
                    question=question_lis[i],
                    llm=llm,
                    retriever_lis=retriever_lis,
                    retrieval_mode=retrieval_mode,
                    locate_mode=locate_mode,
                    generate_mode=generate_mode,
                    remove_duplicate=remove_duplicate
                )
                for retriever in retriever_lis:
                    retriever.back_to_original_ids()

                result_dict = {"question": question_lis[i],
                               "gold sql": gold_sql_lis[i],
                               "database": database_lis[i],
                               "predict_database": database,
                               "retrieve_databases": databases,
                               "is_A": database_lis[i].lower() in [db.lower() for db in databases],
                               "llama_index": predict_schema,
                               }
                results.append(result_dict)

                print(result_dict)
            except Exception as e:
                error_info.append({"question": question_lis[i], "info": str(e)})

        # 保存原始数据和错误信息
        save_path = rf"{log_save_path}\{retrieval_mode}_{locate_mode}_{generate_mode}"
        os.makedirs(save_path, exist_ok=True)
        with open(
                rf"{save_path}\{suffix}_{count}_summary.json",
                'w', encoding="utf-8") as json_file:
            json.dump(results, json_file, indent=4)

        with open(
                rf"{save_path}\{suffix}_{count}_errors_log.json",
                'w', encoding="utf-8") as json_file:
            json.dump(error_info, json_file, indent=4)

        print("\n####  已完成全部数据样本 schema linking!\n")
        # 将结果标准化
        results = cls.transform_result(results, model=llm)

        with open(
                rf"{save_path}\{suffix}_{count}_tr.json",
                'w', encoding="utf-8") as json_file:
            json.dump(results, json_file, indent=4)  # indent=4用于美化输出，使其更易读

        if is_evaluate:
            error_evaluate_run(data=results, mode="precise", save_path=save_path, suffix=f"{suffix}_{count}")

    @classmethod
    def validate_schema_linking(
            cls,
            question: str = None,
            llm=None,
            retriever_lis: List[VectorIndexRetriever] = None,
            retrieval_mode: str = "pipeline",
            # none(all info),norm(llama_index retrieve),pipeline(reason enhance),agent(multi-agent)
            locate_mode: str = "pipeline",  # none(all info,llama_index),pipeline(locate),agent(multi-agent debate)
            generate_mode: str = "pipeline",  # pipeline(single prompt),agent(multi-agent debate)
            remove_duplicate: bool = True
    ):
        """ 返回所有数据库，定位数据库，以及 schema linking 的结果"""
        llm = llm if llm else cls.llm
        turn_n = cls.turn_n

        databases = cls.validate_retrieve_complete(question=question,
                                                   retriever_lis=retriever_lis,
                                                   llm=llm,
                                                   retrieval_mode=retrieval_mode,
                                                   turn_n=turn_n,
                                                   remove_duplicate=remove_duplicate)

        if locate_mode == "none":
            return cls.validate_original_generate(llm, question, databases)

        database = cls.validate_locate(question, databases, locate_mode, turn_n)

        predict_schema = cls.validate_generate(llm, question, database, generate_mode)

        return databases, database, predict_schema

    @classmethod
    def validate_retrieve_complete(
            cls,
            question: str = None,
            retriever_lis: List[VectorIndexRetriever] = None,
            llm=None,
            retrieval_mode: str = "pipeline",
            turn_n: int = 2,
            remove_duplicate: bool = True
    ):
        if retrieval_mode == "none":
            """ 不进行检索，返回全部数据库 """
            index_lis = [retriever.index for retriever in retriever_lis]
            db_lis = []
            for index in index_lis:
                for key, value in index.ref_doc_info.items():
                    file_path = value.metadata["file_path"]
                    db_lis.append(os.path.splitext(os.path.basename(file_path))[0])
            db_lis = list(set(db_lis))

            return db_lis

        if retrieval_mode == "pipeline" or retrieval_mode == "norm":
            databases = SchemaLinkingTool.retrieve_complete(question, retriever_lis, llm,
                                                            open_reason_enhance=(retrieval_mode == "pipeline"),
                                                            open_locate=False,
                                                            output_format="database",
                                                            remove_duplicate=remove_duplicate)
        else:
            databases = SchemaLinkingTool.retrieve_complete_by_multi_agent_debate(question, turn_n, retriever_lis, llm,
                                                                                  open_locate=False,
                                                                                  output_format="database",
                                                                                  remove_duplicate=remove_duplicate)
        return databases

    @classmethod
    def validate_original_generate(
            cls,
            llm=None,
            question: str = None,
            databases: List = None
    ):
        schema_lis = []
        for db in databases:
            with open(ALL_DATABASE_DATA_SOURCE + rf"\{db}.sql", "r", encoding="utf-8") as file:
                schema = file.read().strip()
                schema_lis.append(schema)
        schemas = "\n".join(schema_lis)
        query = VALIDATE_SCHEMA_LINKING_TEMPLATE.format(few_examples=VALIDATE_SCHEMA_LINKING_FEW_EXAMPLES,
                                                        context_str=schemas, question=question)
        answer = llm.complete(query).text
        print(answer)
        db_name = answer[answer.index("<") + 1:answer.index(">")]

        return databases, db_name, answer

    @classmethod
    def validate_locate(
            cls,
            question: str = None,
            databases: List[str] = None,
            locate_mode: str = "pipeline",  # pipeline or agent
            turn_n: int = 2
    ):
        schema_lis = []
        for db in databases:
            with open(ALL_DATABASE_DATA_SOURCE + rf"\{db}.sql", "r", encoding="utf-8") as file:
                schema = file.read().strip().lower()
                schema_lis.append(schema)
        schemas = "\n".join(schema_lis)

        if locate_mode == "agent":
            database = SchemaLinkingTool.locate_with_multi_agent(query=question,
                                                                 context_lis=schema_lis,
                                                                 turn_n=turn_n)
        else:

            database = SchemaLinkingTool.locate(query=question, context=schemas)

        return database

    @classmethod
    def validate_generate(
            cls,
            llm=None,
            question: str = None,
            database: str = None,
            generate_mode: str = "pipeline"

    ):
        if generate_mode == "pipeline":
            with open(ALL_DATABASE_DATA_SOURCE + rf"\{database}.sql", "r", encoding="utf-8") as file:
                schema = file.read().strip()

            query = SCHEMA_LINKING_MANUAL_TEMPLATE.format(few_examples=SCHEMA_LINKING_FEW_EXAMPLES, context_str=schema,
                                                          question=question)
            predict_schema = llm.complete(query).text

            return predict_schema
        else:
            pass

    @classmethod
    def transform_result(cls, data: Union[List, Dict] = None, model=None):
        llm = ZhipuModel() if not model else model

        result_lis = []
        for row in data:
            result_dict = {}
            schema_from_sql = llm.complete(EXTRACT_SCHEMA_FROM_SQL_TEMPLATE.format(sql=row["gold sql"])).text.lower()
            llama_index_schema = llm.complete(
                EXTRACT_SCHEMA_FROM_CONTENT_TEMPLATE.format(schema_links=row["llama_index"])).text.lower()
            # summary_schema = llm.complete(
            #     EXTRACT_SCHEMA_FROM_CONTENT_TEMPLATE.format(schema_links=row["result"]["din-sql"])).text.lower()

            result_dict["question"] = row["question"]
            result_dict["database"] = row["database"]
            result_dict["predict_database"] = row["predict_database"]
            result_dict["retrieve_databases"] = row["retrieve_databases"]
            result_dict["gold sql"] = row["gold sql"]
            result_dict["is_A"] = row["is_A"]
            result_dict["gold schema"] = schema_from_sql
            result_dict["llama_schema"] = llama_index_schema
            # result_dict["summary_schema"] = summary_schema

            result_lis.append(result_dict)

            print(result_dict)

        return result_lis

    @classmethod
    def solve_transform_error(
            cls,
            llm=None,
            save_path: str = None,
            results: List = None,
            suffix: str = None,
    ):
        count = 2150
        # 将结果标准化
        results = cls.transform_result(results, model=llm)

        with open(
                rf"{save_path}\{suffix}_{count}_tr.json",
                'w', encoding="utf-8") as json_file:
            json.dump(results, json_file, indent=4)  # indent=4用于美化输出，使其更易读

        error_evaluate_run(data=results, mode="precise", save_path=save_path, suffix=f"{suffix}_{count}")


def extract_dataset_from_error(data: List):
    df = pd.DataFrame()
    question_lis, sql_lis, database_lis = [], [], []

    for row in data:
        question_lis.append(row["question"])
        sql_lis.append(row["gold sql"])
        database_lis.append(row["database"])

    df["NLQ"] = question_lis
    df["GOLD SQL"] = sql_lis
    df["DATABASE"] = database_lis

    return df


def extract_db_lis_from_results(data: List):
    db_lis = []

    for row in data:
        db_lis.append(row["database"])

    return list(set(db_lis))


def filter_ambiguity():
    ERROR_DIR = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\正式实验\错误分析\errors"

    with open(rf"{ERROR_DIR}\error_A.json", 'r', encoding='utf-8') as file:
        data_a = json.load(file)
    with open(rf"{ERROR_DIR}\error_B.json", 'r', encoding='utf-8') as file:
        data_b = json.load(file)

    data_a = extract_dataset_from_error(data_a)

    data_b = extract_dataset_from_error(data_b)

    with open(
            r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\output\transform\all_db_few_shot_all_tr2.json",
            'r', encoding='utf-8') as file:
        all_results = json.load(file)

    all_db_lis = get_sql_files(
        r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\spider\all_database")

    db_lis = extract_db_lis_from_results(all_results)

    all_data = pd.read_excel(
        r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\dataset\SPIDER_ALL_DATASET.xlsx")
    data = filter_data_by_db(all_data, [db for db in all_db_lis if db not in db_lis])

    result = pd.concat([data_a, data_b, data], ignore_index=True)
    result.to_excel(
        r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\spider\filter_ambiguity.xlsx")


def filter_ambiguity_from_results():
    persist_dir = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\logs\other\norm_none_pipeline"
    save_dir = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\logs\other\question_refine"
    dataset_dir = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\dataset\filter_ambiguity"

    with open(
            rf"{persist_dir}\error_summary_medium.json",
            'r', encoding='utf-8') as file:
        all_results = json.load(file)
    filter_res_lis = []
    for row in all_results:
        if row["type"] in ["1", "2"]:
            filter_res_lis.append(row)
    with open(
            rf"{save_dir}\error_samples_llama.json",
            'w', encoding="utf-8") as json_file:
        json.dump(filter_res_lis, json_file, indent=4)  # indent=4用于美化输出，使其更易读

    df = extract_dataset_from_error(filter_res_lis)

    df.to_excel(rf"{dataset_dir}\filter_ambiguity_hard_pipeline.xlsx")

    return filter_res_lis


if __name__ == "__main__":
    # filter_ambiguity_from_results()
    # ALL_DATABASE_DATA_SOURCE = "E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\spider\hard"
    # vector_index = RagPipeLines.build_index_from_source(
    #     data_source=ALL_DATABASE_DATA_SOURCE,
    #     persist_dir=ALL_DATABASE_DATA_SOURCE + r"\vector_store",
    #     is_vector_store_exist=True,
    #     index_method="VectorStoreIndex"
    # )
    # retriever = RagPipeLines.get_retriever(vector_index)
    #
    # # question = "How many singers do we have?"
    # # nodes = SchemaLinkingTool.retrieve([retriever], [question])
    # # schemas = get_all_schemas_from_schema_text(nodes, "schema", "str")
    # # print(schemas)
    # data = pd.read_excel(
    #     r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\dataset\filter_ambiguity\filter_ambiguity_hard_pipeline.xlsx")
    #
    # data = filter_data_by_db(data, get_sql_files(ALL_DATABASE_DATA_SOURCE))
    # # data = (data
    # #         .sample(200)
    # #         .reset_index()
    # #         .drop(columns=["index"])
    # #         )
    # # print(len(data))
    # print("数据采样完毕")
    #
    api_key = "cff59db1219fd3c205fbe9f210048350.yWIgkhKaQuSWgOVE"
    model_name = "glm-4-air"

    llm = ZhipuModel(api_key=api_key, model_name=model_name)

    # Validate.validate(retriever_lis=[retriever],
    #                   data=data,
    #                   retrieval_mode="pipeline",
    #                   locate_mode="pipeline",
    #                   log_save_path=r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\logs\other",
    #                   suffix="filter_ambiguity")
    save_path = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\logs\other\pipeline_pipeline_pipeline"
    with open(
            rf"{save_path}\filter_ambiguity_2150_summary.json",
            'r', encoding='utf-8') as file:
        all_results = json.load(file)

    Validate.solve_transform_error(
        llm=llm,
        save_path=save_path,
        results=all_results,
        suffix="filter_ambiguity",
    )
