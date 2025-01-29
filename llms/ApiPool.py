from SchemaLinkingCompare.llms.zhipu.ZhipuModel import ZhipuModel


class ZhipuApiPool:
    api_pool_lis = [
        
    ]  # 支持多个 API 调用

    transform_index = 0

    run_llm_index = 16

    @property
    def run_api_key(self):
        return self.api_pool_lis[self.run_llm_index]

    @property
    def transform_api_key(self):
        return self.api_pool_lis[self.transform_index]

    @classmethod
    def handle_run_error(cls):
        if cls.run_llm_index < len(cls.api_pool_lis) - 1:
            cls.run_llm_index += 1

        # assert cls.run_llm_index < len(cls.api_pool_lis)

        return cls.run_llm_index

    @classmethod
    def handle_transform_error(cls):
        if cls.transform_index < len(cls.api_pool_lis) - 1:
            cls.transform_index += 1

            # assert cls.transform_index < len(cls.api_pool_lis)

        return cls.transform_index


if __name__ == "__main__":
    pool = ZhipuApiPool()

    llm = ZhipuModel(api_key=pool.run_api_key, model_name="glm-4-air")

    res = llm.complete("1+1等于几").text
    print(res)
