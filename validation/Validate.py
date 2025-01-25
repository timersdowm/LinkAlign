import json
import os
import pandas as pd
from typing import List, Union, Dict
import concurrent.futures

from llama_index.core.indices.vector_store import VectorIndexRetriever

from SchemaLinkingCompare.config import *
from SchemaLinkingCompare.llms.ApiPool import ZhipuApiPool
from SchemaLinkingCompare.llms.zhipu.ZhipuModel import ZhipuModel
from SchemaLinkingCompare.pipes.RagPipeline import RagPipeLines
from SchemaLinkingCompare.tools.SchemaLinkingTool import SchemaLinkingTool, get_all_schemas_from_schema_text, \
    filter_nodes_by_database
from SchemaLinkingCompare.utils import get_sql_files, parse_json_from_str
from SchemaLinkingCompare.prompts.ValidatePromptsStore import *
from SchemaLinkingCompare.prompts.PropmtsStore import *
from SchemaLinkingCompare.ErrorAnalysis.error_label import error_evaluate_run, parse_tables_from_str
from SchemaLinkingCompare.validation.Generator import GeneratorFactory
from SchemaLinkingCompare.utils import filter_data_by_db
from zhipuai import APIReachLimitError


class Validate:
    """
    一个通用的校验类。
    用于校验给定样本在不同模式下进行 schema linking 的正确率，以及出现四种错误的比例。
    """
    run_model_name = "glm-4-flash"
    transform_model_name = "glm-4-plus"
    max_iter = 6
    pool = ZhipuApiPool()  # 可以替换为其他
    llm = ZhipuModel()
    generator_factory = GeneratorFactory()
    retrieve_turn_n = 1  # 默认不支持参数修改
    locate_turn_n = 1
    generate_turn_n = 2
    link_worker_num = 5
    transform_worker_num = 4
    verbose: bool = True
    linker_num = 3

    @classmethod
    def validate(
            cls,
            llm=None,
            data: pd.DataFrame = None,
            retriever_lis: List[VectorIndexRetriever] = None,  # 外部指定检索数据源
            is_all: bool = True,
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

        def process_question(i, question_lis, llm, retriever_lis, retrieval_mode, locate_mode, generate_mode,
                             remove_duplicate, gold_sql_lis, database_lis, results, error_info):
            max_iter = cls.max_iter
            for _ in range(max_iter):
                try:
                    llm.set_api_key(cls.pool.run_api_key)
                    # llm.set_api_key("7ff727a6f39606898fa5d99a4535a972.tahGD54SmhjkZY4u")
                    llm.model_name = cls.run_model_name

                    databases, database, predict_schema = cls.validate_schema_linking(
                        question=question_lis[i],
                        llm=llm,
                        is_all=is_all,
                        retriever_lis=retriever_lis,
                        retrieval_mode=retrieval_mode,
                        locate_mode=locate_mode,
                        generate_mode=generate_mode,
                        remove_duplicate=remove_duplicate,
                        target_database=database_lis[i]
                    )
                    for retriever in retriever_lis:
                        retriever.back_to_original_ids()

                    # 解析 predict_schema, 如果报错，则将问题捕获
                    predict_schema = predict_schema[predict_schema.rfind("["):predict_schema.rfind("]") + 1]

                    result_dict = {"question": question_lis[i],
                                   "gold sql": gold_sql_lis[i],
                                   "database": database_lis[i],
                                   "predict_database": database,
                                   "retrieve_databases": databases,
                                   "is_A": database_lis[i].lower() in [db.lower() for db in databases],
                                   "llama_index": predict_schema,
                                   }
                    results.append(result_dict)
                    if cls.verbose:
                        print(result_dict)

                    return

                except APIReachLimitError as e:
                    # print(e)
                    msg = parse_json_from_str(e.response.text)["error"]["message"]
                    if msg == "您的账户已欠费，请充值后重试。":
                        ZhipuApiPool.handle_run_error()
                        llm.set_api_key(cls.pool.run_api_key)
                        print(cls.pool.run_api_key)

                except Exception as e:
                    pass
                    # print(e)
                    # return
            print(question_lis[i])
            error_info.append({"question": question_lis[i], "info": "error"})

        def process_questions_in_parallel(count, question_lis, llm, retriever_lis, retrieval_mode, locate_mode,
                                          generate_mode, remove_duplicate, gold_sql_lis, database_lis):
            results, error_info = [], []

            # 使用ThreadPoolExecutor来并行处理问题
            with concurrent.futures.ThreadPoolExecutor(max_workers=cls.link_worker_num) as executor:
                futures = []
                for i in range(count):
                    futures.append(
                        executor.submit(process_question, i, question_lis, llm, retriever_lis, retrieval_mode,
                                        locate_mode, generate_mode, remove_duplicate, gold_sql_lis, database_lis,
                                        results, error_info))

                # 等待所有任务完成
                concurrent.futures.wait(futures)

            return results, error_info

        results, error_info = process_questions_in_parallel(count, question_lis, llm, retriever_lis, retrieval_mode,
                                                            locate_mode, generate_mode, remove_duplicate, gold_sql_lis,
                                                            database_lis)

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
            is_all: bool = True,
            retrieval_mode: str = "pipeline",
            # none(all info),norm(llama_index retrieve),pipeline(reason enhance),agent(multi-agent)
            locate_mode: str = "pipeline",  # none(all info,llama_index),pipeline(locate),agent(multi-agent debate)
            generate_mode: str = "pipeline",  # pipeline(single prompt),agent(multi-agent debate)
            remove_duplicate: bool = True,
            target_database: str = None
    ):
        """ 返回所有数据库，定位数据库，以及 schema linking 的结果"""
        llm = llm if llm else cls.llm

        databases, schemas, nodes = cls.validate_retrieve_complete(question=question,
                                                                   retriever_lis=retriever_lis,
                                                                   llm=llm,
                                                                   is_all=is_all,
                                                                   retrieval_mode=retrieval_mode,
                                                                   turn_n=cls.retrieve_turn_n,
                                                                   remove_duplicate=remove_duplicate)

        if locate_mode == "none":
            if generate_mode == "pipeline":
                return cls.validate_original_generate(llm, question, databases=databases, schemas=schemas)
            else:
                database, predict_schemas = cls.validate_generate_by_schemas(
                    llm=llm,
                    schemas=schemas,
                    question=question,
                    generate_mode=generate_mode,
                    target_database=target_database
                )
                return databases, database, predict_schemas

        database = cls.validate_locate(question=question,
                                       locate_mode=locate_mode,
                                       turn_n=cls.locate_turn_n,
                                       schemas=schemas)
        # print(question, target_database, databases, database)

        if is_all:
            with open(ALL_DATABASE_DATA_SOURCE + rf"\{database}.sql", "r", encoding="utf-8") as file:
                schemas = file.read().strip()
        else:
            schemas = filter_nodes_by_database(nodes, database)

        predict_schema = cls.validate_generate(llm, question=question, generate_mode=generate_mode,
                                               turn_n=cls.generate_turn_n, schemas=schemas)

        return databases, database, predict_schema

    @classmethod
    def validate_generate_by_schemas(
            cls,
            llm=None,
            databases: List = None,  # 可以同时传入database的列表或者schemas的字符串，后者优先级高于前者
            schemas: str = None,
            question: str = None,
            generate_mode: str = None,
            target_database: str = None
    ):
        # 获取全部的 schema
        if not schemas:
            schema_lis = []
            for db in databases:
                with open(ALL_DATABASE_DATA_SOURCE + rf"\{db}.sql", "r", encoding="utf-8") as file:
                    schema = file.read().strip()
                    schema_lis.append(schema)
            schemas = "\n".join(schema_lis)

        generator = cls.generator_factory(generate_mode)
        predict_schema = generator.schema_generate(llm=llm, question=question, schemas=schemas)

        # predict_tables = list(cls.get_column_profiles(llm=llm, schema=predict_schema).keys())
        predict_tables = parse_tables_from_str(predict_schema)

        tables = list(cls.get_column_profiles(llm=llm, database=target_database).keys())

        database = target_database
        # 比较两个schema 是否相同
        for table in predict_tables:
            if table.lower() not in [x.lower() for x in tables]:
                database = "0"
                break

        return database, predict_schema

    @classmethod
    def get_column_profiles(
            cls,
            llm=None,
            database: str = None,
            schema: str = None
    ):
        llm = llm if llm else ZhipuModel()
        prompt = """
请解析下面的全部数据库建表语句，并以标准化的 python json对象格式返回。
### 
数据库建表语句
{context}
###
请输出一个标准的 python json 对象，如下所示：
```json
{{
    "<table name>": {{<column name>:"<belonging table & data type & commentary & example value>"}}
}}
```
输出：
"""
        if not schema:
            with open(ALL_DATABASE_DATA_SOURCE + rf"\{database}.sql", "r", encoding="utf-8") as file:
                schema = file.read().strip()

        query = prompt.format(context=schema)
        res = llm.complete(query).text
        column_profile = parse_json_from_str(res)

        return column_profile

    @classmethod
    def validate_retrieve_complete(
            cls,
            question: str = None,
            retriever_lis: List[VectorIndexRetriever] = None,
            llm=None,
            retrieval_mode: str = "pipeline",
            turn_n: int = 2,
            remove_duplicate: bool = True,
            is_all: bool = True
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
            output = SchemaLinkingTool.retrieve_complete(question, retriever_lis, llm,
                                                         open_reason_enhance=(retrieval_mode == "pipeline"),
                                                         open_locate=False,
                                                         is_all=is_all,
                                                         output_format="all",
                                                         remove_duplicate=remove_duplicate)
        else:
            output = SchemaLinkingTool.retrieve_complete_by_multi_agent_debate(question=question,
                                                                               retrieve_turn_n=turn_n,
                                                                               retriever_lis=retriever_lis,
                                                                               llm=llm,
                                                                               open_locate=False,
                                                                               is_all=is_all,
                                                                               output_format="all",
                                                                               remove_duplicate=remove_duplicate)
        return output

    @classmethod
    def validate_original_generate(
            cls,
            llm=None,
            question: str = None,
            databases: List = None,
            schemas: str = None
    ):
        if not schemas:
            schema_lis = []
            for db in databases:
                with open(ALL_DATABASE_DATA_SOURCE + rf"\{db}.sql", "r", encoding="utf-8") as file:
                    schema = file.read().strip()
                    schema_lis.append(schema)
            schemas = "\n".join(schema_lis)

        query = VALIDATE_SCHEMA_LINKING_TEMPLATE.format(few_examples=VALIDATE_SCHEMA_LINKING_FEW_EXAMPLES,
                                                        context_str=schemas, question=question)
        answer = llm.complete(query).text
        # print(answer)
        db_name = answer[answer.index("<") + 1:answer.index(">")]

        return databases, db_name, answer

    @classmethod
    def validate_locate(
            cls,
            question: str = None,
            databases: List[str] = None,
            locate_mode: str = "pipeline",  # pipeline or agent
            turn_n: int = 2,
            schemas: str = None,
    ):
        schema_lis = []
        if not schemas:
            for db in databases:
                with open(ALL_DATABASE_DATA_SOURCE + rf"\{db}.sql", "r", encoding="utf-8") as file:
                    schema = file.read().strip().lower()
                    schema_lis.append(schema)
            schemas = "\n".join(schema_lis)

        if locate_mode == "agent":
            database = (SchemaLinkingTool
                        .locate_with_multi_agent(query=question,
                                                 context_lis=schema_lis if len(schema_lis) > 0 else [schemas],
                                                 turn_n=turn_n))
        else:

            database = SchemaLinkingTool.locate(query=question, context=schemas)

        return database

    @classmethod
    def validate_generate(
            cls,
            llm=None,
            question: str = None,
            database: str = None,
            generate_mode: str = "pipeline",
            turn_n: int = 2,
            schemas: str = None
    ):
        if not schemas:
            with open(ALL_DATABASE_DATA_SOURCE + rf"\{database}.sql", "r", encoding="utf-8") as file:
                schemas = file.read().strip()

        if generate_mode == "pipeline":

            query = SCHEMA_LINKING_MANUAL_TEMPLATE.format(few_examples=SCHEMA_LINKING_FEW_EXAMPLES, context_str=schemas,
                                                          question=question)
            predict_schema = llm.complete(query).text


        elif generate_mode == "agent":
            predict_schema = SchemaLinkingTool.generate_by_multi_agent(llm=llm,
                                                                       query=question,
                                                                       database=database,
                                                                       context=schemas,
                                                                       turn_n=turn_n,
                                                                       linker_num=cls.linker_num)
        else:
            generator = cls.generator_factory(generate_mode)
            predict_schema = generator.generate(llm=llm, question=question, database=database)

        return predict_schema

    @classmethod
    def transform_result(cls, data: Union[List, Dict] = None, model=None):
        cls.llm = ZhipuModel(model_name=cls.transform_model_name)

        # cls.llm = ZhipuModel(api_key="3e26173069d55eb292f895b4771e9cb9.6j8wX69X6XktYWok", model_name="glm-4-air")

        # llm = ZhipuModel(api_key="4c3bed869f58b820b33da7b042025d1f.QrwcKzDZaaxpEj6N", model_name="glm-4-plus")
        # llm = ZhipuModel(api_key="e918bfb3e3ab45527ef6bcad0b20b4d9.LUvi7Jw6DJpNtlmo", model_name="glm-4-plus")

        # Function to process each row
        def process_row(row):
            max_iter = 5
            for _ in range(max_iter):
                try:
                    cls.llm.set_api_key(api_key=cls.pool.transform_api_key)
                    result_dict = {}
                    schema_from_sql = cls.llm.complete(
                        EXTRACT_SCHEMA_FROM_SQL_TEMPLATE.format(sql=row["gold sql"])).text.lower()
                    schema_from_sql = schema_from_sql[schema_from_sql.rfind("["):schema_from_sql.rfind("]") + 1]

                    llama_index_schema = row["llama_index"]

                    result_dict["question"] = row["question"]
                    result_dict["database"] = row["database"]
                    result_dict["predict_database"] = row["predict_database"]
                    result_dict["retrieve_databases"] = row["retrieve_databases"]
                    result_dict["is_A"] = row["is_A"]
                    result_dict["gold sql"] = row["gold sql"]
                    result_dict["gold schema"] = schema_from_sql
                    result_dict["llama_schema"] = llama_index_schema

                    # print(result_dict)
                    # Return result for further aggregation
                    return result_dict
                except APIReachLimitError as e:
                    msg = parse_json_from_str(e.response.text)["error"]["message"]
                    if msg == "您的账户已欠费，请充值后重试。":
                        ZhipuApiPool.handle_transform_error()
                        cls.llm.set_api_key(api_key=cls.pool.transform_api_key)

                except Exception as e:
                    return None
                    # print(f"Error processing row {row['question']}: {e}")
            return None

        # Using ThreadPoolExecutor to process rows in parallel
        result_lis = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=cls.transform_worker_num) as executor:
            # Map each row in the data to the process_row function
            futures = [executor.submit(process_row, row) for row in data]

            # Collect the results as they complete
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    result_lis.append(result)
                else:
                    print("A row failed processing and was skipped.")

        return result_lis


if __name__ == "__main__":
    vector_index = RagPipeLines.build_index_from_source(
        data_source=ALL_DATABASE_DATA_SOURCE,
        persist_dir=PERSIST_DIR,
        is_vector_store_exist=True,
        index_method="VectorStoreIndex"
    )
    retriever = RagPipeLines.get_retriever(vector_index, similarity_top_k=15)

    # question = "How many singers do we have?"
    # nodes = SchemaLinkingTool.retrieve([retriever], [question])
    # schemas = get_all_schemas_from_schema_text(nodes, "schema", "str")
    # print(schemas)
    data = pd.read_excel(r"F:\benchmark\SPIDER2\data\dataset.xlsx")

    # llm = ZhipuModel()
    # llm = ZhipuModel(model_name="glm-4-flash")
    data = filter_data_by_db(data, get_sql_files(ALL_DATABASE_DATA_SOURCE))
    # data = (data
    #         .sample(10)
    #         .reset_index()
    #         .drop(columns=["index"])
    #         )
    # data.to_excel(
    #     r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\dataset\BIRD_DEV_DATASET.xlsx",
    #     index=False)
    print("数据采样完毕")

    Validate.verbose = False
    # print("#### norm-none-pipeline")
    # Validate.validate(retriever_lis=[retriever],
    #                   data=data,
    #                   is_all=False,
    #                   # llm=llm,
    #                   retrieval_mode="norm",
    #                   locate_mode="none",
    #                   generate_mode="pipeline",
    #                   log_save_path=LOG_DIR,
    #                   suffix="pre_exp")
    # print("\n")

    # print("#### norm-none-din")
    # Validate.validate(retriever_lis=[retriever],
    #                   data=data,
    #                   # llm=llm,
    #                   is_all=False,
    #                   retrieval_mode="norm",
    #                   locate_mode="none",
    #                   generate_mode="din",
    #                   log_save_path=LOG_DIR,
    #                   suffix="01")
    #
    # print("#### norm-none-mac")
    # Validate.validate(retriever_lis=[retriever],
    #                   data=data,
    #                   # llm=llm,
    #                   is_all=False,
    #                   retrieval_mode="norm",
    #                   locate_mode="none",
    #                   generate_mode="mac",
    #                   log_save_path=LOG_DIR,
    #                   suffix="01")
    #
    # print("#### norm-none-mcs")
    # Validate.validate(retriever_lis=[retriever],
    #                   data=data,
    #                   # llm=llm,
    #                   is_all=False,
    #                   retrieval_mode="norm",
    #                   locate_mode="none",
    #                   generate_mode="mcs",
    #                   log_save_path=LOG_DIR,
    #                   suffix="01")

    # print("#### norm-none-c3")
    # Validate.validate(retriever_lis=[retriever],
    #                   data=data,
    #                   # llm=llm,
    #                   is_all=False,
    #                   retrieval_mode="norm",
    #                   locate_mode="none",
    #                   generate_mode="c3",
    #                   log_save_path=LOG_DIR,
    #                   suffix="01")
    #
    # print("#### norm-none-pet")
    # Validate.validate(retriever_lis=[retriever],
    #                   data=data,
    #                   # llm=llm,
    #                   is_all=False,
    #                   retrieval_mode="norm",
    #                   locate_mode="none",
    #                   generate_mode="pet",
    #                   log_save_path=LOG_DIR,
    #                   suffix="01")
    #
    # print("#### pipeline-pipeline-pipeline")
    # Validate.validate(retriever_lis=[retriever],
    #                   data=data,
    #                   # llm=llm,
    #                   is_all=False,
    #                   retrieval_mode="pipeline",
    #                   locate_mode="pipeline",
    #                   generate_mode="pipeline",
    #                   log_save_path=LOG_DIR,
    #                   suffix="01")

    print("#### agent-agent-agent")
    try:
        Validate.validate(retriever_lis=[retriever],
                          data=data,
                          # llm=llm,
                          is_all=False,
                          retrieval_mode="agent",
                          locate_mode="agent",
                          generate_mode="agent",
                          log_save_path=LOG_DIR,
                          suffix="01")
    except Exception as e:
        print(e)

    try:
        print("#### norm-none-rsl")
        Validate.validate(retriever_lis=[retriever],
                          data=data,
                          # llm=llm,
                          is_all=False,
                          retrieval_mode="norm",
                          locate_mode="none",
                          generate_mode="rsl",
                          log_save_path=LOG_DIR,
                          suffix="01")
    except Exception as e:
        print(e)

    try:
        print("#### norm-none-chess")
        Validate.validate(retriever_lis=[retriever],
                          data=data,
                          # llm=llm,
                          is_all=False,
                          retrieval_mode="norm",
                          locate_mode="none",
                          generate_mode="chess",
                          log_save_path=LOG_DIR,
                          suffix="01")
    except Exception as e:
        print(e)
