from retry import retry
from llama_index.core.bridge.pydantic import Field, PrivateAttr
from llama_index.llms.openai_like import OpenAILike


CHAT_MODELS = [
    "rendu-latest",
]


class RenDuLLM(OpenAILike):
    """
    调用RenDu API
    """

    model: str = Field(default="rendu-latest", description="模型名称")
    api_base: str = Field(
        default="https://testapi.aizann.com/v2", description="API Base Url"
    )

    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key=api_key, **kwargs)
        self.is_chat_model = self.model in CHAT_MODELS


def execute_completion(
    system: str = None,
    prompt: str = None,
    response_model: type = None,
    llm_config: dict = None,
    streaming: bool = False,
):
    llm = RenDuLLM(system_prompt=system, is_chat_model=True, **llm_config)
    full_prompt = f"{system or ''}\n{prompt or ''}"
    if streaming:
        response = llm.stream_complete(full_prompt)
    else:
        response = llm.complete(full_prompt)
    print(response)
    return response


@retry(tries=3, delay=2, backoff=2)
async def execute_completion_async(
    system: str,
    prompt: str,
    response_model: type = None,
    llm_config: dict = None,
    streaming: bool = False,
):
    llm = RenDuLLM(system_prompt=system, is_chat_model=True, **llm_config)
    full_prompt = f"{system or ''}\n{prompt or ''}"
    response = await llm.acomplete(full_prompt)
    print(response)
    if not response:
        raise Exception("LLM response is empty")
    return response


if __name__ == "__main__":
    llm = RenDuLLM(
        model="rendu-latest",
        api_key="ba48c211bb384fb6a9ecba7636b6ff7f",
        api_base="http://120.133.68.84:8598/v2",
        is_chat_model=True,
    )
    response = llm.complete("你好，1+1等于几")
    print(response)
