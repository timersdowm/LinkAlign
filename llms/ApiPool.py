from SchemaLinkingCompare.llms.zhipu.ZhipuModel import ZhipuModel


class ZhipuApiPool:
    api_pool_lis = [
        "433952d673f1fdf86aa96700d86f019b.lR1UCi3qtcSl4zCr",
        "7d9f048e4afbb420d6ea1c26a97ad055.1e2VJKqXqyITsseS",
        "8a9992407eace750d799479ae51975b9.M2RFNqUlub1JwzvH",
        "cdeb8bf1d94fe123de6faeb26ff04878.C43m5043fC7QSOyR",
        "b4fa2f7c7438243292f44c746de00351.MsO4zz5OA67ZRrED",
        "bd37091e297a21f414b79e4d0470f4d2.gMA5KGvHqQQdenUY",
        "391c0d9e148c4cb488ae7e33ced0c38b.36vgxbGGMORT5OVg",
        "78c9c3764ea9dc35ac0bf9a3fbb72e89.6XNvIOmNOOGTuk2A",
        "236aa829d380bfdfc564dd069fb2ba6f.s7ONK9ZcuqPoCvPX",
        "2a3200e4fc838ec3bbc38b723ee59afb.lRjTVtMOqsZh8YCs",
        "992044cbafd0a38a97d05d3cca818bdf.vbCSVFULvS1ibVu6",
        "cd6e976ed71d8a1d98728d8755933ee0.9zZISW6kFNAsZC94",
        "533619de354f245891bc8a7db8d3d3a7.XlIxZCSsAngb4Yea",  ##
        "15a39da88fc4f749b9a09d885166665f.K2ljqdl1HbYjnm7p",
        "726910e38c2aedfb98dbffd15381edf8.M0n8gofxg0rVH8jX",
        "e8014d134515828d58f60b8f177c4d5a.sqG1RfzNIwXRy6kn",
        "6b8f24af343889c1c603addb9ffe56e8.BP0ohRrqBm3zT9tb",
        "c4eea42908e4a7481cd82d529ce9546f.JfnFb2zSZeVHrOaI",
        "79c2defe30aec899ed79e9d2c8641f87.H6Av9OfowkpUmctb",
        "ee802c8ced95e64ddc755fbb957521e9.FzcsxRlVAnp38Af4",
        "90aeb371eef06b256c2e2d3762ea0f54.LM7hoPjccdpKnZKL",
        "474282676a5d496182598ae33c20654f.zceGLOmfo2tnh6V6",
        "289a5a09230c4e7f903dfb4a839d0163.29XcHbCh39q8wJVQ",
        "6dd21af07a804ca2b136968cda0f72bd.wWJXXp0bl45dY2vT",
        "6422786fdd024cca896cfcce4985c3ad.Pi6FoGGO6DImukYe",
        "e4724db2a94a4ebb983eb7f798c27e63.0DzPyRzS2VZXaAGd",
        "031815fd28834c9aad7c2f1abd3e2d2c.TdVCD5yRuvlfAine"
        # "7ff727a6f39606898fa5d99a4535a972.tahGD54SmhjkZY4u"
    ]

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
