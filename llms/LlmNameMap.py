from SchemaLinkingCompare.llms.qianfan.QianfanModel import QianfanModel
from SchemaLinkingCompare.llms.zhipu.ZhipuModel import ZhipuModel

llm_map_name_to_model = {
    "zhipu": ZhipuModel,
    "qianfan": QianfanModel
}
# print(llm_map_name_to_model["qianfan"])
