import os
from retry import retry
from llama_index.core.bridge.pydantic import Field, PrivateAttr
from llama_index.core.base.llms.types import MessageRole, ChatMessage
from llama_index.llms.openai_like import OpenAILike


CHAT_MODELS = [
    "rendu-latest",
]
INTENTION_REFERENCE_PROMPT = """
你是一个专业的市场研究分析师，负责判断用户的问题属于哪种研究需求。用户可能提出一个主题、一个问题，或两者结合。

你的任务是：

1. 判断用户的问题是**发散型**（需要广泛查找资料、多角度分析）还是**聚焦型**（寻求具体、明确答案）。
2. 如果是发散型，返回 `2`（适合使用 v2 版本）。
3. 如果是聚焦型，返回 `3`（适合使用 v3 版本）。
4. 只返回一个数字：`2` 或 `3`，不附带解释。

参考示例：
--- 
用户输入：
    当前AIGC内容平台有哪些典型的商业模式？它们未来的发展趋势如何？
输出：
    2
---
用户输入：
    如何评估一家公司的市场规模和市场地位？
输出：
    2
---
用户输入：
    ChatGPT现在支持联网搜索了吗？
输出：
    3
---
用户输入：
    Sora的视频生成速度有多快？
输出：
    3
---

用户的问题是：
{query}
"""


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
    if not response:
        raise Exception("LLM response is empty")
    return response


@retry(tries=3, delay=2, backoff=2)
async def execute_chat_async(
    messages: list,
    response_model: type = None,
    llm_config: dict = None,
    streaming: bool = False,
):
    llm = RenDuLLM(is_chat_model=True, **llm_config)
    format_messages = []
    for index, message in enumerate(messages):
        role = MessageRole.USER if index == 0 else MessageRole.SYSTEM
        format_messages.append(ChatMessage(role=role, content=message))
    response = await llm.achat(format_messages)
    if not response:
        raise Exception("LLM response is empty")
    return response


@retry(tries=3, delay=2, backoff=2)
async def execute_intention_reference_async(
    prompt: str,
    response_model: type = None,
    llm_config: dict = None,
):
    if not llm_config:
        llm_config = {
            "model": os.getenv("CHAT_MODEL_NAME"),
            "api_key": os.getenv("CHAT_MODEL_API_KEY"),
            "api_base": os.getenv("CHAT_MODEL_BASE_URL"),
            "timeout": 600,
        }
    llm = RenDuLLM(system_prompt="", is_chat_model=True, **llm_config)
    full_prompt = INTENTION_REFERENCE_PROMPT.format(query=prompt)
    response = await llm.acomplete(full_prompt)
    if not response:
        raise Exception("LLM response is empty")
    return response_model(response.text)


if __name__ == "__main__":
    llm_config = {
        "model": os.getenv("CHAT_MODEL_NAME"),
        "api_key": os.getenv("CHAT_MODEL_API_KEY"),
        "api_base": os.getenv("CHAT_MODEL_BASE_URL"),
        "timeout": 600,
    }
    llm = RenDuLLM(**llm_config)
    response = llm.complete("你好，1+1等于几")
    print(response)
