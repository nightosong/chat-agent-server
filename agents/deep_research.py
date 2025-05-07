import os
import dirtyjson
import asyncio
import random
from dataclasses import dataclass
from datetime import datetime
from typing import List, Type, TypeVar, Optional, Callable, Union, get_args

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from requests.models import Response
from modules.ai.llms import execute_completion_async
from modules.loggers import logger
from modules.toolkits.firecrawl_mock import FirecrawlMock
from modules.toolkits.firecrawl_serve import FirecrawlService

# region 配置常量及类型
load_dotenv()
T = TypeVar("T", bound=BaseModel)
CONCURRENCY_LIMIT = int(os.environ.get("FIRECRAWL_CONCURRENCY", 50))
# endregion

# region 配置提示词
SYSTEM_PROMPT = """
You are an expert researcher. Today is {now}. Follow these instructions when responding:
  - You may be asked to research subjects that is after your knowledge cutoff, assume the user is right when presented with news.
  - The user is a highly experienced analyst, no need to simplify it, be as detailed as possible and make sure your response is correct.
  - Be highly organized.
  - Suggest solutions that I didn't think about.
  - Be proactive and anticipate my needs.
  - Treat me as an expert in all subject matter.
  - Mistakes erode my trust, so be accurate and thorough.
  - Provide detailed explanations, I'm comfortable with lots of detail.
  - Value good arguments over authorities, the source is irrelevant.
  - Consider new technologies and contrarian ideas, not just the conventional wisdom.
  - You may use high levels of speculation or prediction, just flag it for me.
"""
FEEDBACK_PROMPT = """
Given the following query from the user, ask some follow up questions to clarify the research direction. 
Return a maximum of {num_questions} questions, but feel free to return less if the original query is clear: <query>{query}</query>

You must return the result strictly as a JSON array matching the following schema:
<schema>
```json
{{
    "questions": "list[str], Follow up questions to clarify the research direction, max of {num_questions}"
}}
```
</schema>
"""
SERP_GENERATE_PROMPT = """
Given the following prompt from the user, generate a list of SERP queries to research the topic. 
Return a maximum of {num_queries} queries, but feel free to return less if the original prompt is clear. 
Make sure each query is unique and not similar to each other: <prompt>{query}</prompt>

{learnings_str}

You must return the result strictly as a JSON array matching the following schema:
<schema>
```json
[
  {{
    "query": "string, the SERP query",
    "research_goal": "string, first talk about the goal of the research that this query is meant to accomplish, then go deeper into how to advance the research once the results are found, mention additional research directions. Be as specific as possible, especially for additional research directions."
  }},
  ...
]
```
</schema>
"""
LEARNING_PREFIX_PROMPT = """
Here are some learnings from previous research, use them to generate more specific queries:
{learnings}
"""
SERP_ANALYSIS_PROMPT = """
Given the following contents from a SERP search for the query <query>{query}</query>, generate a list of learnings from the contents. 
Return a maximum of {num_learnings} learnings, but feel free to return less if the contents are clear. Make sure each learning is unique and not similar to each other. 
The learnings should be concise and to the point, as detailed and information dense as possible. 
Make sure to include any entities like people, places, companies, products, things, etc in the learnings, as well as any exact metrics, numbers, or dates. 
The learnings will be used to research the topic further.

<contents>{contents}</contents>

You must return the result strictly as a JSON array matching the following schema:
<schema>
```json
{{
    "learnings": "list[str], List of learnings, max of {num_learnings},
    "follow_up_questions": "list[str], List of follow-up questions to research the topic further, max of {num_follow_up}"
}}
```
</schema>
"""
FINAL_REPORT_PROMPT = """
Given the following prompt from the user, write a final report on the topic using the learnings from research. 
Make it as as detailed as possible, aim for 3 or more pages, include ALL the learnings from research:

<prompt>{prompt}</prompt>

Here are all the learnings from previous research:

<learnings>
{learnings_str}
</learnings>

You must return the result strictly as a JSON array matching the following schema:
<schema>
```json
{{
    "report_markdown": "str, Final report on the topic in Markdown format, make it as detailed as possible, aim for 3 or more pages, include ALL the learnings from research."
}}
```
</schema>
"""
FINAL_ANSWER_PROMPT = """
Given the following prompt from the user, write a final answer on the topic using the learnings from research. 
Follow the format specified in the prompt. Do not yap or babble or include any other text than the answer besides the format specified in the prompt. 
Keep the answer as concise as possible - usually it should be just a few words or maximum a sentence. 
Try to follow the format specified in the prompt (for example, if the prompt is using Latex, the answer should be in Latex. 
If the prompt gives multiple answer choices, the answer should be one of the choices).

<prompt>{prompt}</prompt>

Here are all the learnings from research on the topic that you can use to help answer the prompt:

<learnings>
{learnings_str}
</learnings>

You must return the result strictly as a JSON array matching the following schema:
<schema>
```json
{{
    "exact_answer": "str, The final answer, make it short and concise, just the answer, no other text."
}}
```
</schema>
"""
# endregion

# 初始化FirecrawlApp
# firecrawl = FirecrawlService(api_url=os.environ.get("FIRECRAWL_BASE_URL"))
firecrawl = FirecrawlMock()


@dataclass
class ResearchProgress:
    current_depth: int
    total_depth: int
    current_breadth: int
    total_breadth: int
    current_query: Optional[str] = None
    total_queries: int = 0
    completed_queries: int = 0


@dataclass
class ResearchResult:
    learnings: List[str]
    visited_urls: List[str]


class FeedbackQuery(BaseModel):
    questions: List[str] = Field(..., max_items=5)


class SerpQuery(BaseModel):
    query: str
    research_goal: str = Field(..., description="研究目标和后续方向")


class ProcessResult(BaseModel):
    learnings: List[str] = Field(..., max_items=3)
    follow_up_questions: List[str] = Field(..., max_items=3)


class FinalReport(BaseModel):
    report_markdown: str


class ExactAnswer(BaseModel):
    exact_answer: str


class DeepResearchAgent:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT.format(now=str(datetime.now()))

    async def waitting_for_feedback(self, prompt: str) -> Union[None, str]:
        return None

    async def generate_object(
        self, prompt: str, response_model: Type[T]
    ) -> Union[T, List[T]]:
        llm_config = {
            "model": os.getenv("CHAT_MODEL_NAME"),
            "api_key": os.getenv("CHAT_MODEL_API_KEY"),
            "api_base": os.getenv("CHAT_MODEL_BASE_URL"),
            "timeout": 600,
        }
        retries = 3
        for attempt in range(retries):
            try:
                response = await execute_completion_async(
                    system=self.system_prompt,
                    prompt=prompt,
                    response_model=response_model,
                    llm_config=llm_config,
                )
                if not response.text:
                    raise ValueError("Empty response from LLM")
            except Exception as e:
                logger.error(f"Error generating object: {e}")
                if attempt < retries - 1:
                    logger.info(f"Retrying... ({attempt + 1}/{retries})")
                    await asyncio.sleep(1)
                else:
                    raise
        logger.info(f"send query: {prompt}")
        response_text: str = str(response.text).strip()
        if response_text.startswith("```json"):
            response_text = response_text.strip("```json").strip("```").strip()
        logger.info(f"model response: {response_text}")
        results = dirtyjson.loads(response_text)
        if isinstance(results, dict):
            return response_model(**results)
        elif isinstance(results, list):
            item_model = get_args(response_model)[0]
            return list(item_model(**item) for item in results)
        raise ValueError(f"Invalid response format: {response_text}")

    async def generate_feedback_queries(self, query: str) -> FeedbackQuery:
        prompt = FEEDBACK_PROMPT.format(query=query, num_questions=5)
        result = await self.generate_object(prompt=prompt, response_model=FeedbackQuery)
        return result

    async def generate_serp_queries(
        self, query: str, num_queries: int = 3, learnings: Optional[List[str]] = None
    ) -> List[SerpQuery]:
        learnings_str = (
            (LEARNING_PREFIX_PROMPT + chr(10).join(f"- {l}" for l in learnings))
            if learnings
            else ""
        )
        prompt = SERP_GENERATE_PROMPT.format(
            query=query, num_queries=num_queries, learnings_str=learnings_str
        )

        results = await self.generate_object(
            prompt=prompt, response_model=List[SerpQuery]
        )
        logger.info(f"生成{len(results)}个查询: ...")
        return results

    async def process_page_content(self, markdown_content: str) -> str:
        # 编写调用 LLM 的 prompt
        prompt = f"""请对以下 Markdown 内容进行精炼清洗，去除杂乱的符号，并提取内容摘要，确保不遗漏重要信息：\n{markdown_content}"""
        llm_config = {
            "model": os.getenv("CHAT_MODEL_NAME"),
            "api_key": os.getenv("CHAT_MODEL_API_KEY"),
            "api_base": os.getenv("CHAT_MODEL_BASE_URL"),
            "timeout": 600,
        }
        # 调用 LLM 进行处理
        response = await execute_completion_async(
            "", prompt=prompt, response_model=str, llm_config=llm_config
        )

        return response.text

    async def process_serp_result(
        self,
        query: str,
        contents: List[str],
        num_learnings: int = 3,
        num_follow_up: int = 3,
    ) -> ProcessResult:
        logger.info(f"处理查询[{query}]，找到{len(contents)}条内容")

        analysis_prompt = SERP_ANALYSIS_PROMPT.format(
            query=query,
            contents=chr(10).join(contents),
            num_learnings=num_learnings,
            num_follow_up=num_follow_up,
        )

        results = await self.generate_object(
            prompt=analysis_prompt, response_model=ProcessResult
        )
        return results

    async def write_final_report(
        self, prompt: str, learnings: List[str], urls: List[str]
    ) -> str:
        learnings_str = chr(10).join(f"<learning>{l}</learning>" for l in learnings)

        report = await self.generate_object(
            prompt=FINAL_REPORT_PROMPT.format(
                prompt=prompt, learnings_str=learnings_str
            ),
            response_model=FinalReport,
        )

        return f"{report.report_markdown}\n\n## 数据源\n{chr(10).join(f'- {u}' for u in urls)}"

    async def write_final_answer(self, prompt: str, learnings: List[str]) -> str:
        answer = await self.generate_object(
            prompt=FINAL_ANSWER_PROMPT.format(prompt=prompt, learnings_str=learnings),
            response_model=ExactAnswer,
        )
        return answer.exact_answer

    async def deep_research(
        self,
        query: str,
        breadth: int,
        depth: int,
        learnings: Optional[List[str]] = None,
        visited_urls: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[ResearchProgress], None]] = None,
    ) -> ResearchResult:
        progress = ResearchProgress(
            current_depth=depth,
            total_depth=depth,
            current_breadth=breadth,
            total_breadth=breadth,
        )

        async def update_progress(**kwargs):
            nonlocal progress
            for k, v in kwargs.items():
                setattr(progress, k, v)
            if progress_callback:
                progress_callback(progress)

        async def process_query(serp_query: SerpQuery):
            logger.info(
                f"Processing SERP query: {serp_query.query}, research goal: {serp_query.research_goal}"
            )
            async with self.semaphore:
                await update_progress(current_query=serp_query.query)

                try:
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    search_result = await firecrawl.search_async(
                        serp_query.query,
                        params={
                            "limit": 5,
                            "scrape_options": {"formats": ["markdown"]},
                            # "timeout": 150
                        },
                    )
                    logger.info(f"Search result: {search_result}")
                    logger.info(
                        f"查询[{serp_query.query}]结果：{len(search_result.data or [])}条"
                    )
                    tasks = [
                        asyncio.create_task(
                            self.process_page_content(item["description"])
                        )
                        for item in search_result.data
                        if item["description"]
                    ]

                    contents = await asyncio.gather(*tasks)
                    logger.info(f"Process page completed: {contents}")
                    analysis_result = await self.process_serp_result(
                        serp_query.query, contents
                    )

                    new_urls = [
                        item["url"] for item in search_result.data if item["url"]
                    ]
                    all_urls = list(set(new_urls + (visited_urls or [])))
                    all_learnings = list(
                        set((learnings or []) + analysis_result.learnings)
                    )
                    logger.info(f"Related urls: {all_urls}")
                    logger.info(f"Process serp result completed: {analysis_result}")

                    if depth > 1:
                        next_query = f"""
                        Previous research goal: {serp_query.research_goal}
                        Follow-up research directions: {chr(10).join(analysis_result.follow_up_questions)}
                        """.strip()

                        return await self.deep_research(
                            query=next_query,
                            breadth=(breadth + 1) // 2,
                            depth=depth - 1,
                            learnings=all_learnings,
                            visited_urls=all_urls,
                            progress_callback=progress_callback,
                        )

                    await update_progress(
                        completed_queries=progress.completed_queries + 1,
                        current_depth=0,
                    )
                    logger.info(
                        f"查询[{serp_query.query}]完成，获得{len(all_learnings)}个学习结果"
                    )
                    return ResearchResult(
                        learnings=all_learnings, visited_urls=all_urls
                    )

                except Exception as e:
                    logger.info(f"查询[{serp_query.query}]错误：{str(e)}")
                    return ResearchResult(learnings=[], visited_urls=[])

        queries = await self.generate_serp_queries(query, breadth, learnings)
        await update_progress(total_queries=len(queries))

        results = await asyncio.gather(*[process_query(q) for q in queries])
        print(results)
        return ResearchResult(
            learnings=list({l for r in results for l in r.learnings}),
            visited_urls=list({u for r in results for u in r.visited_urls}),
        )

    async def run(self, initial_query: str, breadth=4, depth=2, is_report=True) -> str:
        logger.info("Creating research plan...")

        # Generate follow-up questions
        feedback_result = await self.generate_feedback_queries(query=initial_query)

        logger.info(
            "To better understand your research needs, please answer these follow-up questions:"
        )
        logger.info(chr(10).join(f"- {q}" for q in feedback_result.questions))

        # Collect answers to follow-up questions
        follow_up_questions_str = ""
        for question in feedback_result.questions:
            answer = await self.waitting_for_feedback(question)
            if not answer:
                continue
            follow_up_questions_str += f"Q: {question}\nA: {answer}\n"

        # Combine all information for deep research
        follow_up_questions_str = (
            "Follow-up Questions and Answers:" + follow_up_questions_str
            if follow_up_questions_str
            else ""
        )
        combined_query = f"Initial Query: {initial_query}\n{follow_up_questions_str}"

        logger.info("Starting research...")

        research_result = await self.deep_research(
            query=combined_query, breadth=breadth, depth=depth
        )
        logger.info("Research completed.")
        logger.info(f"Total learnings: {len(research_result.learnings)}")
        logger.info(f"Total visited URLs: {len(research_result.visited_urls)}")
        learnings = research_result.learnings

        if is_report:
            final_result = await self.write_final_report(
                combined_query, learnings, research_result.visited_urls
            )
        else:
            final_result = await self.write_final_answer(combined_query, learnings)
        return final_result


if __name__ == "__main__":
    agent = DeepResearchAgent()
    result = asyncio.run(
        agent.run(
            initial_query="What are the latest developments in AI?",
            breadth=4,
            depth=2,
            is_report=True,
        )
    )
    print(result)
