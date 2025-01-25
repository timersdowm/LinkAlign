import asyncio
from collections import Counter

from SchemaLinkingCompare.config import *
from SchemaLinkingCompare.pipes.RagPipeline import RagPipeLines
from SchemaLinkingCompare.tools.SchemaLinkingTool import SchemaLinkingTool
from SchemaLinkingCompare.prompts.PropmtsStore import *
from SchemaLinkingCompare.llms.zhipu.ZhipuModel import ZhipuModel
from SchemaLinkingCompare.tools.SchemaLinkingTool import SchemaLinkingTool
from SchemaLinkingCompare.utils import *

from SchemaLinkingCompare.validation.PromptStore import *
from abc import ABC, abstractmethod


class BaseGenerator(ABC):
    llm = ZhipuModel()

    @abstractmethod
    def generate(self):
        pass

    @abstractmethod
    def schema_generate(self):
        pass


class DinGenerator(BaseGenerator):
    @classmethod
    def generate(
            cls,
            llm=None,
            question: str = None,
            database: str = None
    ):
        llm = llm if llm else cls.llm

        with open(ALL_DATABASE_DATA_SOURCE + rf"\{database}.sql", "r", encoding="utf-8") as file:
            schemas = file.read().strip()

        query = DIN_SCHEMA_LINKING_TEMPLATE.format(few_examples=SCHEMA_LINKING_FEW_EXAMPLES,
                                                   context_str=schemas, question=question)
        predict_schema = llm.complete(query).text

        return predict_schema

    @classmethod
    def schema_generate(
            cls,
            llm=None,
            question: str = None,
            schemas: str = None,
    ):
        llm = llm if llm else cls.llm
        query = DIN_SCHEMA_LINKING_TEMPLATE.format(few_examples=SCHEMA_LINKING_FEW_EXAMPLES,
                                                   context_str=schemas, question=question)
        predict_schema = llm.complete(query).text

        return predict_schema


class MultiAgentDebateGenerator(BaseGenerator):
    turn_n = 1
    linker_num = 2

    @classmethod
    def generate(
            cls,
            llm=None,
            question: str = None,
            database: str = None
    ):
        llm = llm if llm else cls.llm

        with open(ALL_DATABASE_DATA_SOURCE + rf"\{database}.sql", "r", encoding="utf-8") as file:
            schema = file.read().strip()
        predict_schema = SchemaLinkingTool.generate_by_multi_agent(llm=llm,
                                                                   query=question,
                                                                   database=database,
                                                                   context=schema,
                                                                   turn_n=cls.turn_n,
                                                                   linker_num=cls.linker_num)
        return predict_schema

    @classmethod
    def schema_generate(
            cls,
            llm=None,
            question: str = None,
            schemas: str = None,
    ):
        llm = llm if llm else cls.llm
        predict_schema = SchemaLinkingTool.generate_by_multi_agent(llm=llm,
                                                                   query=question,
                                                                   context=schemas,
                                                                   turn_n=cls.turn_n,
                                                                   linker_num=cls.linker_num)
        return predict_schema


class MacGenerator(BaseGenerator):

    @classmethod
    def generate(
            cls,
            llm=None,
            question: str = None,
            database: str = None
    ):
        llm = llm if llm else cls.llm

        with open(ALL_DATABASE_DATA_SOURCE + rf"\{database}.sql", "r", encoding="utf-8") as file:
            schema = file.read().strip()

        query = MAC_SCHEMA_LINKING_TEMPLATE.format(context=schema, question=question)
        predict_schema = llm.complete(query).text

        return predict_schema

    @classmethod
    def schema_generate(
            cls,
            llm=None,
            question: str = None,
            schemas: str = None
    ):
        llm = llm if llm else cls.llm

        query = MAC_SCHEMA_LINKING_TEMPLATE.format(context=schemas, question=question)
        predict_schema = llm.complete(query).text

        return predict_schema


class McsGenerator(BaseGenerator):

    @classmethod
    def generate(
            cls,
            llm=None,
            question: str = None,
            database: str = None
    ):
        llm = llm if llm else cls.llm

        with open(ALL_DATABASE_DATA_SOURCE + rf"\{database}.sql", "r", encoding="utf-8") as file:
            schema = file.read().strip()

        table_select_query = MCS_TABLE_LINKING_TEMPLATE.format(context=schema, question=question)

        table_lis = asyncio.run(cls.llm_complete(llm, table_select_query, parser_name="tables"))

        col_profiles = cls.get_column_profiles(llm=llm, database=database)

        schema_string = "###"

        for table, columns in col_profiles.items():
            if table in table_lis:
                schema_string += f"\n# Table Name: {table}\n"
                for col, desc in columns.items():
                    schema_string += f"{col}:{desc}\n"

        column_select_query = MCS_COLUMN_LINKING_TEMPLATE.format(context=schema_string, question=question)
        # res = llm.complete(column_select_query).text
        # predict_schema = parse_json_from_str(res)["columns"]
        predict_schema = asyncio.run(cls.llm_complete(llm=llm, query=column_select_query, parser_name="columns"))

        predict_schema = "[" + ",".join(predict_schema) + "]"
        return predict_schema

    @classmethod
    def schema_generate(
            cls,
            llm=None,
            question: str = None,
            schemas: str = None
    ):
        llm = llm if llm else cls.llm
        table_select_query = MCS_TABLE_LINKING_TEMPLATE.format(context=schemas, question=question)

        table_lis = asyncio.run(cls.llm_complete(llm, table_select_query, parser_name="tables"))

        col_profiles = cls.get_column_profiles(llm=llm, schema=schemas)

        schema_string = "###"

        for table, columns in col_profiles.items():
            if table in table_lis:
                schema_string += f"\n# Table Name: {table}\n"
                for col, desc in columns.items():
                    schema_string += f"{col}:{desc}\n"

        column_select_query = MCS_COLUMN_LINKING_TEMPLATE.format(context=schema_string, question=question)
        # res = llm.complete(column_select_query).text
        # predict_schema = parse_json_from_str(res)["columns"]
        predict_schema = asyncio.run(cls.llm_complete(llm=llm, query=column_select_query, parser_name="columns"))

        predict_schema = "[" + ",".join(predict_schema) + "]"
        return predict_schema

    @classmethod
    async def llm_complete(
            cls,
            llm=None,
            query: str = None,
            n=2,
            parser_name: str = None
    ):
        response = []

        async def process():
            try:
                res = llm.complete(query).text
                target_res = parse_json_from_str(res)[parser_name]
                assert type(target_res) == list
                response.extend(target_res)

            except Exception as e:
                pass

        tasks = [process() for _ in range(n)]

        # Run the tasks concurrently
        await asyncio.gather(*tasks)

        return response

    @classmethod
    def get_column_profiles(
            cls,
            llm=None,
            schema: str = None,
            database: str = None
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


class ChessGenerator(BaseGenerator):

    @classmethod
    def generate(
            cls,
            llm=None,
            question: str = None,
            database: str = None
    ):
        llm = llm if llm else cls.llm

        column_profiles = cls.get_column_profiles(llm=llm, database=database)

        list_of_kwargs = []
        for table_name, columns in column_profiles.items():
            for column_name, column_profile in columns.items():
                kwargs = {
                    "QUESTION": question,
                    "COLUMN_PROFILE": column_profile,
                }
                list_of_kwargs.append(kwargs)

        response = asyncio.run(cls.process_kwargs(llm, list_of_kwargs))
        # response = []
        # for kwargs in list_of_kwargs:
        #     query = CHESS_FILTER_COLUMN_TEMPLATE.format(
        #         COLUMN_PROFILE=kwargs["COLUMN_PROFILE"],
        #         QUESTION=kwargs["QUESTION"])
        #     res = parse_json_from_str(llm.complete(query).text)
        #     response.append(res)

        tentative_schema = {}
        index = 0
        for table_name, columns in column_profiles.items():
            tentative_schema[table_name] = []
            for column_name, column_profile in columns.items():
                try:
                    chosen = (response[index]["is_column_information_relevant"].lower() == "yes")
                    if chosen:
                        tentative_schema[table_name].append(column_name)
                except Exception as e:
                    print(e)
                index += 1

        schema_string = "###"

        for table, columns in tentative_schema.items():
            if len(columns) != 0:
                schema_string += f"\n# Table Name: {table}\n"
                for col in columns:
                    col_file = column_profiles[table][col]
                    schema_string += f"{col}:{col_file}\n"

        query = CHESS_SELECT_TABLE_TEMPLATE.format(DATABASE_SCHEMA=schema_string, QUESTION=question)

        tables = parse_json_from_str(llm.complete(query).text)["table_names"]

        schema_string = "###"

        for table, columns in tentative_schema.items():
            if table in tables:
                schema_string += f"\n# Table Name: {table}\n"
                for col in columns:
                    col_file = column_profiles[table][col]
                    schema_string += f"{col}:{col_file}\n"

        query = CHESS_SELECT_COLUMN_TEMPLATE.format(DATABASE_SCHEMA=schema_string, QUESTION=question)

        res = parse_json_from_str(llm.complete(query).text)
        schema_lis = []
        for key, value in res.items():
            if key != "chain_of_thought_reasoning" and len(value) > 0:
                for col in value:
                    schema_lis.append(f"{key}.{col}")

        predict_schemas = "[" + ",".join(schema_lis) + "]"

        return predict_schemas

    @classmethod
    def schema_generate(
            cls,
            llm=None,
            question: str = None,
            schemas: str = None
    ):
        llm = llm if llm else cls.llm

        column_profiles = cls.get_column_profiles(llm=llm, schema=schemas)

        list_of_kwargs = []
        for table_name, columns in column_profiles.items():
            for column_name, column_profile in columns.items():
                kwargs = {
                    "QUESTION": question,
                    "COLUMN_PROFILE": column_profile,
                }
                list_of_kwargs.append(kwargs)

        response = asyncio.run(cls.process_kwargs(llm, list_of_kwargs))

        tentative_schema = {}
        index = 0
        for table_name, columns in column_profiles.items():
            tentative_schema[table_name] = []
            for column_name, column_profile in columns.items():
                try:
                    chosen = (response[index]["is_column_information_relevant"].lower() == "yes")
                    if chosen:
                        tentative_schema[table_name].append(column_name)
                except Exception as e:
                    print(e)
                index += 1

        schema_string = "###"

        for table, columns in tentative_schema.items():
            if len(columns) != 0:
                schema_string += f"\n# Table Name: {table}\n"
                for col in columns:
                    col_file = column_profiles[table][col]
                    schema_string += f"{col}:{col_file}\n"

        query = CHESS_SELECT_TABLE_TEMPLATE.format(DATABASE_SCHEMA=schema_string, QUESTION=question)

        tables = parse_json_from_str(llm.complete(query).text)["table_names"]

        schema_string = "###"

        for table, columns in tentative_schema.items():
            if table in tables:
                schema_string += f"\n# Table Name: {table}\n"
                for col in columns:
                    col_file = column_profiles[table][col]
                    schema_string += f"{col}:{col_file}\n"

        query = CHESS_SELECT_COLUMN_TEMPLATE.format(DATABASE_SCHEMA=schema_string, QUESTION=question)

        res = parse_json_from_str(llm.complete(query).text)
        schema_lis = []
        for key, value in res.items():
            if key != "chain_of_thought_reasoning" and len(value) > 0:
                for col in value:
                    schema_lis.append(f"{key}.{col}")

        predict_schemas = "[" + ",".join(schema_lis) + "]"

        return predict_schemas

    @classmethod
    async def process_kwargs(
            cls,
            llm=None,
            list_of_kwargs: List = None
    ):
        llm = llm if llm else cls.llm
        response = []

        # Define a coroutine for processing each kwargs entry
        async def process_entry(kwargs):
            try:
                query = CHESS_FILTER_COLUMN_TEMPLATE.format(
                    COLUMN_PROFILE=kwargs["COLUMN_PROFILE"],
                    QUESTION=kwargs["QUESTION"]
                )
                res = await llm.acomplete(query)  # Use the async acomplete method here
                # Assuming 'res' is a 'CompletionResponse' object, access its 'text' or 'output'
                response.append(parse_json_from_str(res.text))  # Or res.output depending on your actual class
            except Exception as e:
                pass

        # Create a list of tasks for asynchronous execution
        tasks = [process_entry(kwargs) for kwargs in list_of_kwargs]

        # Run the tasks concurrently
        await asyncio.gather(*tasks)

        return response

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


class C3Generator(BaseGenerator):
    @classmethod
    def generate(
            cls,
            llm=None,
            question: str = None,
            database: str = None
    ):
        llm = llm if llm else ZhipuModel()
        column_profiles = cls.get_column_profiles(llm=llm, database=database)

        with open(ALL_DATABASE_DATA_SOURCE + rf"\{database}.sql", "r", encoding="utf-8") as file:
            schema = file.read().strip()

        query = C3_TABLE_RECALL_TEMPLATE.format(context=schema, question=question)
        table_list = asyncio.run(cls.llm_complete(llm=llm, query=query))

        tables_sc = []
        for table in table_list:
            table_exist = table if len(table) < 4 else table[:4]  # 这块为啥默认最大数量只能为 4 呢
            tables_sc.append(table_exist)

        counts = Counter(tuple(sorted(lst)) for lst in tables_sc)
        tables, count = counts.most_common(1)[0]

        tables = list(tables)

        schema_string = "###"
        for table, columns in column_profiles.items():
            if table in tables:
                schema_string += f"\n# Table Name: {table}\n"
                for col, profile in columns.items():
                    schema_string += f"{col}:{profile}\n"

        query = C3_COLUMN_RECALL_TEMPLATE.format(context=schema_string, question=question)

        column_lis = asyncio.run(cls.llm_complete(llm=llm, query=query))

        columns = []
        for column in column_lis:
            exist_columns = column if len(column) < 4 else column[:4]
            columns.extend(exist_columns)

        columns = [col.lower() for col in columns]
        columns = list(set(columns))

        return "[" + ",".join(columns) + "]"

    @classmethod
    def schema_generate(
            cls,
            llm=None,
            question: str = None,
            schemas: str = None
    ):
        llm = llm if llm else ZhipuModel()
        column_profiles = cls.get_column_profiles(llm=llm, schema=schemas)

        query = C3_TABLE_RECALL_TEMPLATE.format(context=schemas, question=question)

        table_list = asyncio.run(cls.llm_complete(llm=llm, query=query))

        tables_sc = []
        for table in table_list:
            table_exist = table if len(table) < 4 else table[:4]  # 这块为啥默认最大数量只能为 4 呢
            tables_sc.append(table_exist)

        counts = Counter(tuple(sorted(lst)) for lst in tables_sc)
        tables, count = counts.most_common(1)[0]

        tables = list(tables)

        schema_string = "###"
        for table, columns in column_profiles.items():
            if table in tables:
                schema_string += f"\n# Table Name: {table}\n"
                for col, profile in columns.items():
                    schema_string += f"{col}:{profile}\n"

        query = C3_COLUMN_RECALL_TEMPLATE.format(context=schema_string, question=question)

        column_lis = asyncio.run(cls.llm_complete(llm=llm, query=query))

        columns = []
        for column in column_lis:
            exist_columns = column if len(column) < 4 else column[:4]
            columns.extend(exist_columns)

        columns = [col.lower() for col in columns]
        columns = list(set(columns))

        return "[" + ",".join(columns) + "]"

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
    async def llm_complete(
            cls,
            llm=None,
            query: str = None,
            n=2,
    ):
        response = []

        async def process():
            try:
                res = llm.complete(query).text
                target_res = paser_list_from_str(res)
                assert type(target_res) == list
                response.append(target_res)

            except Exception as e:
                pass

        tasks = [process() for _ in range(n)]

        # Run the tasks concurrently
        await asyncio.gather(*tasks)

        return response


class PetGenerator(BaseGenerator):
    FILE_PATH = r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\validation\SchemaLinkingValidate\sample_datas"

    vector_index = RagPipeLines.build_index_from_source(
        data_source=FILE_PATH,
        persist_dir=FILE_PATH + r"\vector_store",
        is_vector_store_exist=True,
        index_method="VectorStoreIndex"
    )

    @classmethod
    def generate(
            cls,
            llm=None,
            question: str = None,
            database: str = None
    ):
        llm = llm if llm else ZhipuModel()
        with open(ALL_DATABASE_DATA_SOURCE + rf"\{database}.sql", "r", encoding="utf-8") as file:
            schema = file.read().strip()

        # 检索相似的样本，直接用 llama index 检索了

        query = PET_GENERATE_PRE_SQL_TEMPLATE.format(schema=schema, question=question)

        engine = RagPipeLines.get_query_engine(index=cls.vector_index, query_template=query, similarity_top_k=1)

        predict_sql = engine.query(question)

        predict_schema = llm.complete(
            EXTRACT_SCHEMA_FROM_SQL_TEMPLATE.format(sql=predict_sql)).text.lower()

        # print(predict_schema)

        return predict_schema

    @classmethod
    def schema_generate(
            cls,
            llm=None,
            question: str = None,
            schemas: str = None
    ):
        llm = llm if llm else ZhipuModel()

        # 检索相似的样本，直接用 llama index 检索了

        query = PET_GENERATE_PRE_SQL_TEMPLATE.format(schema=schemas, question=question)

        engine = RagPipeLines.get_query_engine(index=cls.vector_index, query_template=query, similarity_top_k=1)

        predict_sql = engine.query(question).response

        predict_schema = llm.complete(
            EXTRACT_SCHEMA_FROM_SQL_TEMPLATE.format(sql=predict_sql)).text.lower()

        # print(predict_schema)
        return predict_schema


class RslGenerator(BaseGenerator):
    @classmethod
    def generate(
            cls,
            llm=None,
            question: str = None,
            database: str = None
    ):
        llm = llm if llm else ZhipuModel()
        with open(ALL_DATABASE_DATA_SOURCE + rf"\{database}.sql", "r", encoding="utf-8") as file:
            schemas = file.read().strip()

        prompt = RSL_TABLE_COLUMN_SELECTION_TEMPLATE.format(schema=schemas, question=question)

        pre_schemas = parse_json_from_str(llm.complete(prompt).text)

        sql = cls.preliminary_sql(llm=llm, schemas=schemas, database=database, table_column=pre_schemas,question=question)["sql"]

        post_schema = llm.complete(
            EXTRACT_SCHEMA_FROM_SQL_TEMPLATE.format(sql=sql)).text.lower()

        post_schema = "[" + post_schema[post_schema.rfind("[") + 1:post_schema.rfind("]")] + "," + ",".join(
            pre_schemas["columns"]) + "]"

        return post_schema

    @classmethod
    def preliminary_sql(cls, llm=None, schemas=None, database="", table_column=None, question=None):
        llm = llm if llm else ZhipuModel()

        table_info = "\n\n### Answer the question by sqlite SQL query only and with no explanation. You must minimize SQL execution time while ensuring correctness.\n" + f"""### Here are all the table creation statements for the SQLite '{database}' database, including tables, their properties, data information, and foreign key details for table joins.
{schemas}\n""" + f'### tables: {table_column["tables"]}\n' + f'### columns: {table_column["columns"]}\n'

        table_info += "\n### Question: " + question + "\n### Only output json object as your answer."

        prompt = RSL_SQL_GENERATION_INSTRUCTION + table_info
        answer = llm.complete(prompt).text
        try:
            answer = parse_json_from_str(answer)
        except Exception as e:
            print(e)
            answer = answer.replace("\\", "\\\\")
            answer = json.loads(answer)
            answer = answer['sql'].replace('\n', ' ')
        return answer

    @classmethod
    def schema_generate(
            cls,
            llm=None,
            question: str = None,
            schemas: str = None
    ):
        llm = llm if llm else ZhipuModel()

        prompt = RSL_TABLE_COLUMN_SELECTION_TEMPLATE.format(schema=schemas, question=question)

        pre_schemas = parse_json_from_str(llm.complete(prompt).text)

        sql = cls.preliminary_sql(llm=llm, schemas=schemas, table_column=pre_schemas,question=question)["sql"]

        post_schema = llm.complete(
            EXTRACT_SCHEMA_FROM_SQL_TEMPLATE.format(sql=sql)).text.lower()

        post_schema = "[" + post_schema[post_schema.rfind("[") + 1:post_schema.rfind("]")] + "," + ",".join(
            pre_schemas["columns"]) + "]"

        return post_schema


class GeneratorFactory:
    def __call__(self, generator_type="din", *args, **kwargs):
        if generator_type == "din":
            return DinGenerator()
        elif generator_type == "agent":
            return MultiAgentDebateGenerator()
        elif generator_type == "mac":
            return MacGenerator()
        elif generator_type == "mcs":
            return McsGenerator()
        elif generator_type == "chess":
            return ChessGenerator()
        elif generator_type == "c3":
            return C3Generator()
        elif generator_type == "pet":
            return PetGenerator()
        elif generator_type == "rsl":
            return RslGenerator()


if __name__ == "__main__":
    question = "What is the maximum capacity and the average of all stadiums ?"
    database = "concert_singer"
    llm = ZhipuModel(model_name="glm-4-flash")
    schema = RslGenerator.generate(llm=llm, question=question, database=database)
    print(schema)
