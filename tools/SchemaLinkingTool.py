# -*- coding: utf-8 -*-

"""
数据库的范围决定了 Schema Linking 的难度。过往文献实验通常在单个数据库上进行，但实际场景中往往并不清楚所在的数据库。从数据库的范围可以分成两个方面，单一数据库 和 所有数据库，后者需要对数据库的所有表信息进行拼接。
另一方面，提示方法同样有两类，zero-shot 和 few-shot ，实验同样需要比较不同提示方法的差异。
此外，还需要比较不同模型的性能....
"""
import asyncio
from datetime import datetime
from llama_index.core.indices.vector_store import VectorIndexRetriever

from SchemaLinkingCompare.config import *
from SchemaLinkingCompare.llms.zhipu.ZhipuModel import ZhipuModel
from typing import Union, List
from llama_index.core import (
    SummaryIndex,
    VectorStoreIndex,
    Settings,
    QueryBundle,

)
from llama_index.core.indices.utils import default_format_node_batch_fn
from llama_index.core.schema import NodeWithScore, TextNode, MetadataMode
from llama_index.core.base.base_retriever import BaseRetriever
from SchemaLinkingCompare.prompts.PropmtsStore import *
from SchemaLinkingCompare.pipes.RagPipeline import RagPipeLines
from SchemaLinkingCompare.prompts.MultiAgentDebatePromptStore import *


def filter_nodes_by_database(
        nodes: List[NodeWithScore],
        database: Union[str, List],
        output_format: str = "str"
) -> str:
    schema_lis = []
    for node in nodes:
        file_path = node.node.metadata["file_path"]
        db = file_path.split("\\")[-1].split(".")[0].strip()
        if type(database) == str:
            if db == database:
                schema_lis.append(default_format_node_batch_fn([node.node]))
        elif type(database) == List:
            if db in database:
                schema_lis.append(default_format_node_batch_fn([node.node]))
    if output_format == "str":
        return "\n".join(schema_lis)

    return schema_lis


def get_all_schemas_from_schema_text(
        nodes: List[NodeWithScore],
        output_format: str = "database",  # database or schema
        schemas_format: str = "str",
        is_all: bool = True
):
    databases = []

    for node in nodes:
        file_path = node.node.metadata["file_path"]
        db = file_path.split("\\")[-1].split(".")[0].strip()
        databases.append(db)

    databases = list(set(databases))

    if output_format == "database":
        return databases

    if is_all:
        schemas = []
        for db in databases:
            with open(ALL_DATABASE_DATA_SOURCE + rf"\{db}.sql", "r", encoding="utf-8") as file:
                schema = file.read().strip()
                schemas.append(schema)

        if schemas_format == "str":
            schemas = "\n".join(schemas)
    else:
        summary_nodes = nodes
        fmt_node_txts = []
        for idx in range(len(summary_nodes)):
            file_path = summary_nodes[idx].node.metadata["file_path"]
            db = file_path.split("\\")[-1].split(".")[0].strip()
            fmt_node_txts.append(
                f"### Database Name: {db}\n#Following is the table creation statement for the database {db}\n"
                f"{summary_nodes[idx].get_content(metadata_mode=MetadataMode.LLM)}"
            )
        schemas = "\n\n".join(fmt_node_txts)

    if output_format == "all":
        return databases, schemas, nodes
    else:
        return schemas


def get_sub_ids(
        nodes: List[NodeWithScore],
        index_lis: List[VectorStoreIndex],
        is_all: bool = True
):
    if is_all:
        file_name_lis = []
        for node in nodes:
            file_name = node.node.metadata["file_name"]
            file_name_lis.append(file_name)

        sub_ids = []
        duplicate_ids = []
        for index in index_lis:
            doc_info_dict = index.ref_doc_info
            for key, ref_doc_info in doc_info_dict.items():
                if ref_doc_info.metadata["file_name"] not in file_name_lis:
                    sub_ids.extend(ref_doc_info.node_ids)
                else:
                    duplicate_ids.extend(ref_doc_info.node_ids)

        return sub_ids
    else:
        exist_node_ids = [node.node.id_ for node in nodes]
        all_ids = []
        for index in index_lis:
            doc_info_dict = index.ref_doc_info
            for key, ref_doc_info in doc_info_dict.items():
                all_ids.extend(ref_doc_info.node_ids)
        sub_ids = [id_ for id_ in all_ids if id_ not in exist_node_ids]

        return sub_ids


def get_ids_from_source(
        source: Union[List[VectorStoreIndex], List[NodeWithScore]]
):
    node_ids = []
    """ 本方法仅用于解析本实验需要两种类型的 node_id """
    for data in source:
        if isinstance(data, VectorStoreIndex):
            doc_info_dict = data.ref_doc_info
            for key, ref_doc_info in doc_info_dict.items():
                node_ids.extend(ref_doc_info.node_ids)

        elif isinstance(data, NodeWithScore):

            node_ids.append(data.node.node_id)

    # 去重
    node_ids = list(set(node_ids))

    return node_ids


class SchemaLinkingTool:
    @classmethod
    def link_schema_by_question(
            cls,
            llm: ZhipuModel = None,
            index: Union[SummaryIndex, VectorStoreIndex] = None,
            is_add_example: bool = True,
            question: str = None,
            similarity_top_k: int = 5,
            **kwargs
    ) -> str:
        if not index:
            raise Exception("输入参数中索引不能为空！")

        if not question:
            raise Exception("输入参数中用户查询问题不能为空！")

        llm = llm if llm else ZhipuModel()

        Settings.llm = llm

        few_examples = SCHEMA_LINKING_FEW_EXAMPLES if is_add_example else ""

        query_template = SCHEMA_LINKING_TEMPLATE.format(few_examples=few_examples, question=question)

        engine_args = {
            "index": index,
            "query_template": query_template,
            "similarity_top_k": similarity_top_k,  # todo 文本块的数量可能需要动态确定
            **kwargs
        }

        engine = RagPipeLines.get_query_engine(**engine_args)

        response = engine.query(question).response

        return response

    @classmethod
    def retrieve(
            cls,
            retriever_lis: List[BaseRetriever],
            query_lis: List[Union[str, QueryBundle]]
    ) -> List[NodeWithScore]:
        """ 串行化检索 """
        nodes_lis = []

        for retriever in retriever_lis:
            for query in query_lis:
                nodes = retriever.retrieve(query)
                nodes_lis.extend(nodes)

        nodes_lis.sort(key=lambda x: x.score, reverse=True)

        return nodes_lis

    @classmethod
    def parallel_retrieve(
            cls,
            retriever_lis: List[BaseRetriever],  # 每个 retriever 的不同之处在于建立索引的源文档不同，而非同个数据库
            query_lis: List[Union[str, QueryBundle]]  #
    ) -> List[NodeWithScore]:
        async def retrieve_from_single_retriever(retriever: BaseRetriever, query: Union[str, QueryBundle]):
            nodes = await retriever.aretrieve(query)
            return nodes

        # 初始化事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 为每个检索器创建任务，并在事件循环中运行它们
            tasks = ([loop.create_task(retrieve_from_single_retriever(retriever, query))
                      for query in query_lis
                      for retriever in retriever_lis])
            # 使用 loop.run_until_complete 函数协调所有任务
            results = loop.run_until_complete(asyncio.gather(*tasks))
        finally:
            # 确保事件循环在完成后关闭
            loop.close()

        # 扁平化结果列表
        nodes_lis = [node for sublist in results for node in sublist]

        # 排序结果
        nodes_lis.sort(key=lambda x: x.score, reverse=True)

        return nodes_lis

    @classmethod
    def reason_enhance(
            cls,
            llm=None,
            query: str = None
    ):
        """ 利用大模型在问题的基础上进行推理，并返回推理分析的结果 """
        if not query:
            raise Exception("输入的查询不能为空！")

        llm = llm if llm else ZhipuModel()

        prompt = REASON_ENHANCE_TEMPLATE.format(query=query)

        reason_query = llm.complete(prompt=prompt).text  # 增强后的问题查询

        return reason_query

    @classmethod
    def judge(
            cls,
            llm: None,
            query: str = None,
            context: str = None
    ):
        pass

    @classmethod
    def locate(
            cls,
            llm=None,
            query: str = None,
            context: str = None  # 检索的所有数据库schema
    ) -> str:

        """ 从不同数据库中根据语义推理，将问题映射到唯一的数据库上 """

        if not query:
            raise Exception("输入的查询不能为空！")

        llm = llm if llm else ZhipuModel()

        prompt = LOCATE_TEMPLATE.format(query=query, context=context)

        # print(prompt)
        database = llm.complete(prompt=prompt).text  # 增强后的问题查询
        #
        return database

    @classmethod
    def locate_with_multi_agent(
            cls,
            llm=None,
            turn_n: int = 2,
            query: str = None,
            nodes: List[NodeWithScore] = None,
            context_lis: List[str] = None,

    ) -> str:
        if not query:
            raise Exception("输入的查询不能为空！")

        llm = llm if llm else ZhipuModel()

        if context_lis:
            pass
        elif not context_lis and nodes:
            context_lis = get_all_schemas_from_schema_text(nodes, output_format="schema", schemas_format="list")
        else:
            raise Exception("输入参数中没有包含 database schemas")

        context_str = ""
        for ind, context in enumerate(context_lis):
            context_str += f"""
[The Start of Candidate Database"{ind + 1}"'s Schema]
{context}
[The End of Candidate Database"{ind + 1}"'s Schema]
            """
        source_text = SOURCE_TEXT_TEMPLATE.format(query=query, context_str=context_str)

        chat_history = []

        # one-by-one
        for i in range(turn_n):
            data_analyst_prompt = FAIR_EVAL_DEBATE_TEMPLATE.format(
                source_text=source_text,
                chat_history="\n".join(chat_history),
                role_description=DATA_ANALYST_ROLE_DESCRIPTION,
                agent_name="data analyst"
            )
            data_analyst_debate = llm.complete(data_analyst_prompt).text
            chat_history.append(f"""
[Debate Turn: {i + 1}, Agent Name:"data analyst", Debate Content:{data_analyst_debate}]
            """)

            data_scientist_prompt = FAIR_EVAL_DEBATE_TEMPLATE.format(
                source_text=source_text,
                chat_history="\n".join(chat_history),
                role_description=DATABASE_SCIENTIST_ROLE_DESCRIPTION,
                agent_name="data scientist"
            )
            data_scientist_debate = llm.complete(data_scientist_prompt).text
            chat_history.append(f"""
[Debate Turn: {i + 1}, Agent Name:"data scientist", Debate Content:{data_scientist_debate}]
            """)

        # print(chat_history)
        summary_prompt = FAIR_EVAL_DEBATE_TEMPLATE.format(
            source_text=source_text,
            chat_history="\n".join(chat_history),
            role_description=SUMMARY_TEMPLATE,
            agent_name="debate terminator"
        )

        database = llm.complete(summary_prompt).text

        # print(chat_history)

        return database

    @classmethod
    def locate_with_multi_agent2(
            cls,
            llm=None,
            turn_n: int = 2,
            query: str = None,
            nodes: List[NodeWithScore] = None,
            context_lis: List[str] = None,
            size=4
    ) -> str:
        if not query:
            raise Exception("输入的查询不能为空！")

        llm = llm if llm else ZhipuModel()

        if context_lis:
            pass
        elif not context_lis and nodes:
            context_lis = get_all_schemas_from_schema_text(nodes, output_format="schema", schemas_format="list")
        else:
            raise Exception("输入参数中没有包含 database schemas")

        def filter_database(sub_context_lis) -> str:
            context_str = ""
            for ind, context in enumerate(sub_context_lis):
                context_str += f"""
[The Start of Candidate Database"{ind + 1}"'s Schema]
{context}
[The End of Candidate Database"{ind + 1}"'s Schema]
                    """
                source_text = SOURCE_TEXT_TEMPLATE.format(query=query, context_str=context_str)

                chat_history = []

                # one-by-one
                for i in range(turn_n):
                    data_analyst_prompt = FAIR_EVAL_DEBATE_TEMPLATE.format(
                        source_text=source_text,
                        chat_history="\n".join(chat_history),
                        role_description=DATA_ANALYST_ROLE_DESCRIPTION,
                        agent_name="data analyst"
                    )
                    data_analyst_debate = llm.complete(data_analyst_prompt).text
                    chat_history.append(f"""
            [Debate Turn: {i + 1}, Agent Name:"data analyst", Debate Content:{data_analyst_debate}]
                        """)

                    data_scientist_prompt = FAIR_EVAL_DEBATE_TEMPLATE.format(
                        source_text=source_text,
                        chat_history="\n".join(chat_history),
                        role_description=DATABASE_SCIENTIST_ROLE_DESCRIPTION,
                        agent_name="data scientist"
                    )
                    data_scientist_debate = llm.complete(data_scientist_prompt).text
                    chat_history.append(f"""
            [Debate Turn: {i + 1}, Agent Name:"data scientist", Debate Content:{data_scientist_debate}]
                        """)

                summary_prompt = FAIR_EVAL_DEBATE_TEMPLATE.format(
                    source_text=source_text,
                    chat_history="\n".join(chat_history),
                    role_description=SUMMARY_TEMPLATE,
                    agent_name="debate terminator"
                )

                database = llm.complete(summary_prompt).text

                return database

        def chunk_list(lst, chunk_size):
            """将列表lst等分成指定长度chunk_size的多个子列表"""
            return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

        database = ""
        while len(context_lis) > 1:
            sub_context_lis_lis = chunk_list(context_lis, chunk_size=size)
            db_lis = []
            for scl in sub_context_lis_lis:
                db_lis.append(filter_database(scl))
            if len(db_lis) == 0:
                database = db_lis[0]
            context_lis = filter_nodes_by_database(nodes, db_lis)

        # print(chat_history)

        return database

    @classmethod
    def retrieve_complete(
            cls,
            question: str = None,
            retriever_lis: List[VectorIndexRetriever] = None,
            llm=None,
            open_reason_enhance: bool = True,
            open_locate: bool = False,  # 测试一般设置为关闭，正式实验可以开启
            open_agent_debate: bool = False,  # 只有在open_locate 为真时该参数生效
            turn_n: int = 2,
            output_format: str = "database",  # database or schema,前者输出数据库名称，后者输出该数据库的 schema 信息
            remove_duplicate: bool = True,  # 在已检索出 node 以外的范围检索，效率可能有损失
            is_all: bool = True,
    ):
        """ 尽管方法名仅体现 retrieval ,但可以通过 open_locate 参数开启端到端的数据库定位的功能"""

        if not question:
            raise Exception("输入参数中问题不能为空！")
        elif not retriever_lis:
            raise Exception("输入参数中索引列表不能为空！")

        llm = llm if llm else ZhipuModel()

        if not open_reason_enhance:
            """ 如果不进行推理增强，仅使用 LlamaIndex 提供的检索功能"""
            nodes = cls.parallel_retrieve(retriever_lis, [question])

        else:
            if not remove_duplicate:
                """ 如果不进行去重，同时使用 Question 和增强后的问题进行检索 """
                analysis = cls.reason_enhance(llm=llm, query=question)  # 调用大模型，通过推理对原始问题进行增强

                enhanced_question = question + analysis

                nodes = cls.parallel_retrieve(retriever_lis, [question, enhanced_question])

            else:
                # 获取所有的 index 和 id 列表
                index_lis = [ret.index for ret in retriever_lis]

                question_nodes = cls.parallel_retrieve(retriever_lis, [question])

                sub_ids = get_sub_ids(question_nodes, index_lis, is_all=is_all)

                # 设置新的id
                for ret in retriever_lis:
                    ret.change_node_ids(sub_ids)

                # 进行问题增强
                analysis = cls.reason_enhance(llm=llm, query=question)  # 调用大模型，通过推理对原始问题进行增强
                enhanced_question = question + analysis

                enhance_question_nodes = cls.parallel_retrieve(retriever_lis, [enhanced_question])

                for ret in retriever_lis:
                    ret.back_to_original_ids()

                nodes = question_nodes + enhance_question_nodes

        if open_locate:
            """ 若进行数据库定位 """
            if open_agent_debate:
                predict_database = cls.locate_with_multi_agent(llm=llm, query=question, nodes=nodes, turn_n=turn_n)
            else:
                schemas = get_all_schemas_from_schema_text(nodes=nodes, output_format='schema')
                predict_database = cls.locate(llm=llm, query=question, context=schemas)

            return predict_database

        else:
            output = get_all_schemas_from_schema_text(nodes=nodes, output_format=output_format,
                                                      schemas_format="str", is_all=is_all)

            return output

    @classmethod
    def retrieve_complete_by_multi_agent_debate(
            cls,
            question: str = None,
            retrieve_turn_n: int = 2,
            locate_turn_n: int = 2,
            retriever_lis: List[VectorIndexRetriever] = None,
            llm=None,
            open_locate: bool = False,  # 测试一般设置为关闭，正式实验可以开启,locate 只能输出唯一的 database
            open_agent_debate: bool = False,
            output_format: str = "database",  # database or schema,前者输出数据库名称，后者输出该数据库的 schema 信息
            remove_duplicate: bool = True,  # 在已检索出 node 以外的范围检索，效率可能有损失
            is_all: bool = True
    ):
        if not question:
            raise Exception("输入参数中问题不能为空！")
        elif not retriever_lis:
            raise Exception("输入参数中索引列表不能为空！")

        llm = llm if llm else ZhipuModel()

        enhanced_question = question
        question_nodes = cls.parallel_retrieve(retriever_lis, [question])
        nodes = question_nodes
        # 获取所有的 index 和 id 列表
        index_lis = [ret.index for ret in retriever_lis]

        sub_ids = get_ids_from_source(nodes)

        for _ in range(retrieve_turn_n):
            if not remove_duplicate:
                # 这里没有将检索范围设置为 sub_ids
                nodes += cls.parallel_retrieve(retriever_lis, [enhanced_question])

            else:
                # 设置新的id
                for ret in retriever_lis:
                    ret.change_node_ids(sub_ids)

                enhance_question_nodes = cls.parallel_retrieve(retriever_lis, [enhanced_question])
                nodes += enhance_question_nodes

                sub_ids = get_sub_ids(nodes, index_lis, is_all)

                # 恢复原来的 id
                for ret in retriever_lis:
                    ret.back_to_original_ids()

            schemas = get_all_schemas_from_schema_text(nodes=nodes, output_format='schema', is_all=is_all)

            """ 
            下面使用 multi-agent debate 的方式进行，共有两个角色，judge 和 annotator。
            judge 负责分析错误并给出分析，而 annotator 主要负责为问题添加注释
            """
            # judge 进行分析
            analysis = llm.complete(JUDGE_TEMPLATE.format(question=question, context=schemas)).text

            # annotator 添加注释
            annotation = llm.complete(ANNOTATOR_TEMPLATE.format(question=question, analysis=analysis)).text

            enhanced_question = annotation
            # print(annotation)

        if not remove_duplicate:
            nodes += cls.parallel_retrieve(retriever_lis, [enhanced_question])
        else:
            # 设置新的id
            for ret in retriever_lis:
                ret.change_node_ids(sub_ids)

            enhance_question_nodes = cls.parallel_retrieve(retriever_lis, [enhanced_question])
            nodes += enhance_question_nodes

            # 恢复原来的 id
            for ret in retriever_lis:
                ret.back_to_original_ids()

        if open_locate:
            """ 若进行数据库定位 """
            if open_agent_debate:
                predict_database = cls.locate_with_multi_agent(llm=llm, query=question, nodes=nodes,
                                                               turn_n=locate_turn_n)
            else:
                schemas = get_all_schemas_from_schema_text(nodes=nodes, output_format='schema', is_all=is_all)
                predict_database = cls.locate(llm=llm, query=question, context=schemas)

            return predict_database

        else:
            output = get_all_schemas_from_schema_text(nodes=nodes, output_format=output_format, is_all=is_all)

            return output

    @classmethod
    def schema_linking(
            cls,
            question: str = None,
            llm=None,
            turn_n: int = 2,
            retriever_lis: List[VectorIndexRetriever] = None,
            remove_duplicate: bool = True,
            retrieval_mode: str = "agent",  # 两种检索方式，pipeline 或者 agent
            open_agent_debate: bool = False,
            generate_mode: str = "agent"
    ) -> str:
        if not question:
            raise Exception("输入参数中问题不能为空！")
        elif not retriever_lis:
            raise Exception("输入参数中索引列表不能为空！")

        if retrieval_mode not in ["pipeline", "agent"]:
            raise Exception("输入参数中检索模式不正确！")

        llm = llm if llm else ZhipuModel()

        if retrieval_mode == "pipeline":
            database = SchemaLinkingTool.retrieve_complete(question, retriever_lis, llm, open_locate=True,
                                                           remove_duplicate=remove_duplicate,
                                                           open_agent_debate=open_agent_debate)
        else:
            database = SchemaLinkingTool.retrieve_complete_by_multi_agent_debate(question, turn_n, retriever_lis, llm,
                                                                                 open_locate=True,
                                                                                 remove_duplicate=remove_duplicate,
                                                                                 open_agent_debate=open_agent_debate
                                                                                 )
        with open(ALL_DATABASE_DATA_SOURCE + rf"\{database.lower()}.sql", "r", encoding="utf-8") as file:
            schema = file.read().strip()

        if generate_mode == "agent":
            predict_schema = cls.generate_by_multi_agent(llm=llm, query=question, context=schema, turn_n=turn_n)
        else:
            query = SCHEMA_LINKING_MANUAL_TEMPLATE.format(few_examples=SCHEMA_LINKING_FEW_EXAMPLES, context_str=schema,
                                                          question=question)
            predict_schema = llm.complete(query).text

        return predict_schema

    @classmethod
    def generate_by_multi_agent(
            cls,
            llm=None,
            query: str = None,
            database: str = None,
            context: str = None,
            turn_n: int = 2,
            linker_num: int = 1  # schema linker 角色的数量
    ):
        llm = llm if llm else ZhipuModel()

        if context is None:
            with open(ALL_DATABASE_DATA_SOURCE + rf"\{database.lower()}.sql", "r", encoding="utf-8") as file:
                context = file.read().strip()
        context_str = f"""
[The Start of Database Creation Statements]
{context}
[The End of Database Creation Statements]
"""
        source_text = GENERATE_SOURCE_TEXT_TEMPLATE.format(query=query, context_str=context_str)

        chat_history = []

        # one-by-one
        for i in range(turn_n):
            data_analyst_prompt = GENERATE_FAIR_EVAL_DEBATE_TEMPLATE.format(
                source_text=source_text,
                chat_history="\n".join(chat_history),
                role_description=GENERATE_DATA_ANALYST_ROLE_DESCRIPTION,
                agent_name="data analyst"
            )
            for j in range(linker_num):
                data_analyst_debate = llm.complete(data_analyst_prompt).text
                chat_history.append(f"""
[Debate Turn: {i + 1}, Agent Name:"data analyst {j}", Debate Content:{data_analyst_debate}]
""")
            data_scientist_prompt = GENERATE_FAIR_EVAL_DEBATE_TEMPLATE.format(
                source_text=source_text,
                chat_history="\n".join(chat_history),
                role_description=GENERATE_DATABASE_SCIENTIST_ROLE_DESCRIPTION,
                agent_name="data scientist"
            )
            data_scientist_debate = llm.complete(data_scientist_prompt).text
            chat_history.append(f"""
[Debate Turn: {i + 1}, Agent Name:"data scientist", Debate Content:{data_scientist_debate}]
""")

        summary_prompt = GENERATE_FAIR_EVAL_DEBATE_TEMPLATE.format(
            source_text=source_text,
            chat_history="\n".join(chat_history),
            role_description=GENERATE_SUMMARY_TEMPLATE,
            agent_name="debate terminator"
        )

        schema = llm.complete(summary_prompt).text

        # print(chat_history)

        return schema

    @classmethod
    def pipeline(
            cls,
            llm=None,
            question: str = None,
            retriever_lis: List[VectorIndexRetriever] = None,

    ):
        #  Step one: Reduce Noise by Response Filtering
        index_lis = [ret.index for ret in retriever_lis]

        question_nodes = cls.parallel_retrieve(retriever_lis, [question])

        sub_ids = get_sub_ids(question_nodes, index_lis)

        # 设置新的id
        for ret in retriever_lis:
            ret.change_node_ids(sub_ids)

        # 进行问题增强
        analysis = cls.reason_enhance(llm=llm, query=question)  # 调用大模型，通过推理对原始问题进行增强
        enhanced_question = question + analysis

        enhance_question_nodes = cls.parallel_retrieve(retriever_lis, [enhanced_question])

        for ret in retriever_lis:
            ret.back_to_original_ids()

        nodes = question_nodes + enhance_question_nodes


#
if __name__ == "__main__":
    #     import pandas as pd
    # #
    #     data = pd.read_excel(
    #         r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\dataset\SPIDER_DEV_DATASET.xlsx")

    vector_index = RagPipeLines.build_index_from_source(
        data_source=ALL_DATABASE_DATA_SOURCE,
        persist_dir=PERSIST_DIR,
        is_vector_store_exist=True,
        index_method="VectorStoreIndex"
    )
    import pandas as pd
    from SchemaLinkingCompare.utils import *

    # data = pd.read_excel(
    #     r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\benchmark\hard\dataset_v5.xlsx")
    #
    # # llm = ZhipuModel(api_key="e918bfb3e3ab45527ef6bcad0b20b4d9.LUvi7Jw6DJpNtlmo", model_name="glm-4-plus")
    #
    # data = filter_data_by_db(data, get_sql_files(ALL_DATABASE_DATA_SOURCE))
    retriever = RagPipeLines.get_retriever(index=vector_index, similarity_top_k=5)
    # question_lis = list(data["NLQ"])
    # database_lis = list(data["DATABASE"])
    # sql_lis = list(data["GOLD SQL"])
    # question = "How many orders were from Hanna Moos company in 1999? # Helpful Evidence: \"Hanna Moos\" is the CompanyName; in 1999 refer to YEAR (OrderDate) = 1999"
    # question = "What is the average height in centimeters of all the players in the position of defense? # Helpful Evidence: average = AVG(height_in_cm); players refers to PlayerName; position of defense refers to position_info = 'D'"
    # database = "ice_hockey_draft"
    # database = SchemaLinkingTool.retrieve_complete(
    #     question=question,
    #     retriever_lis=[retriever],
    #     # open_reason_enhance=True,
    #     open_locate=True
    # )
    # with open(
    #         r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\logs\bird\agent_agent_agent\error2.json",
    #         'r', encoding='utf-8') as file:
    #     data = json.load(file)
    data = pd.read_excel(r"E:\在校学习\科研\大模型环境下数据查询语言生成通用性的研究\code\SchemaLinkingCompare\data\dataset\refine_question\refined_question(filter_by_sql_length).xlsx")
    count = 0
    question_lis = list(data["NLQ"])
    for ques in question_lis:
        print(ques)
        predict_db = SchemaLinkingTool.retrieve_complete_by_multi_agent_debate(
            ques,
            retriever_lis=[retriever],
            is_all=True,
            open_locate=False,
            open_agent_debate=True,
            retrieve_turn_n=3,
            locate_turn_n=2
        )
    # import concurrent.futures
    #
    #
    # # Function to process each sample
    # def process_sample(sample):
    #     predict_db = SchemaLinkingTool.retrieve_complete_by_multi_agent_debate(
    #         question,
    #         retriever_lis=[retriever],
    #         is_all=True,
    #         open_locate=True,
    #         open_agent_debate=True,
    #         retrieve_turn_n=1,
    #         locate_turn_n=2
    #     )
    #     print(sample["database"], predict_db)
    #     if sample["database"] == predict_db:
    #         return 1  # Increment count if the condition is met
    #     return 0
    #
    #
    # # Main function to process data with multithreading
    # def process_data(data):
    #     with concurrent.futures.ThreadPoolExecutor() as executor:
    #         # Submit each sample to the thread pool and process them concurrently
    #         results = executor.map(process_sample, data)
    #
    #         # Sum up the results to get the final count
    #         count = sum(results)
    #
    #     return count


    # Example usage
    # a = process_data(data)
    # print("Final count:", a)
    # print(predict_db)
    # res = SchemaLinkingTool.generate_by_multi_agent(query=question,
    #                                                 database=database,
    #                                                 turn_n=1,
    #                                                 linker_num=2)
    # predict_schema = res[res.rfind("["):res.rfind("]") + 1]
    # # print(question_lis[1])
    # # print(sql_lis[1])
    # # print(database_lis[1])
    # print(res)
    # print(predict_schema)
