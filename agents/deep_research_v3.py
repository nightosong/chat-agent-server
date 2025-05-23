import os
import json
import asyncio
import operator
import queue
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Annotated
from modules.ai.llms import execute_completion, execute_completion_async
from modules.web.base_engine import SearchEngine, SearchResult
from modules.loggers import logger

TASK_DONE = "__DONE__"
# region 提示词
QUERY_WRITER_INSTRUCTIONS = """Your goal is to generate a targeted web search query.

<CONTEXT>
Current date: {current_date}
Please ensure your queries account for the most current information available as of this date.
</CONTEXT>

<TOPIC>
{research_topic}
</TOPIC>

<FORMAT>
Format your response as a JSON object with ALL three of these exact keys:
   - "query": The actual search query string
   - "rationale": Brief explanation of why this query is relevant
</FORMAT>

<EXAMPLE>
Example output:
{{
    "query": "machine learning transformer architecture explained",
    "rationale": "Understanding the fundamental structure of transformer models"
}}
</EXAMPLE>

Provide your response in JSON format:"""

SUMMARIZER_INSTRUCTIONS = """
<GOAL>
Generate a high-quality summary of the provided context.
</GOAL>

<REQUIREMENTS>
When creating a NEW summary:
1. Highlight the most relevant information related to the user topic from the search results
2. Ensure a coherent flow of information

When EXTENDING an existing summary:                                                                                                                 
1. Read the existing summary and new search results carefully.                                                    
2. Compare the new information with the existing summary.                                                         
3. For each piece of new information:                                                                             
    a. If it's related to existing points, integrate it into the relevant paragraph.                               
    b. If it's entirely new but relevant, add a new paragraph with a smooth transition.                            
    c. If it's not relevant to the user topic, skip it.                                                            
4. Ensure all additions are relevant to the user's topic.                                                         
5. Verify that your final output differs from the input summary.                                                                                                                                                            
< /REQUIREMENTS >

< FORMATTING >
- Start directly with the updated summary, without preamble or titles. Do not use XML tags in the output.  
< /FORMATTING >

<Task>
Think carefully about the provided Context first. Then generate a summary of the context to address the User Input.
</Task>
"""

REFLECTION_INSTRUCTIONS = """You are an expert research assistant analyzing a summary about {research_topic}.

<GOAL>
1. Identify knowledge gaps or areas that need deeper exploration
2. Generate a follow-up question that would help expand your understanding
3. Focus on technical details, implementation specifics, or emerging trends that weren't fully covered
</GOAL>

<REQUIREMENTS>
Ensure the follow-up question is self-contained and includes necessary context for web search.
</REQUIREMENTS>

<FORMAT>
Format your response as a JSON object with these exact keys:
- knowledge_gap: Describe what information is missing or needs clarification
- follow_up_query: Write a specific question to address this gap
</FORMAT>

<Task>
Reflect carefully on the Summary to identify knowledge gaps and produce a follow-up query. Then, produce your output following this JSON format:
{{
    "knowledge_gap": "The summary lacks information about performance metrics and benchmarks",
    "follow_up_query": "What are typical performance benchmarks and metrics used to evaluate [specific technology]?"
}}
</Task>

Provide your analysis in JSON format:"""
# endregion


def get_current_date():
    return datetime.now().strftime("%B %d, %Y")


def format_sources(search_results: List[SearchResult]) -> str:
    return "\n".join(f"* {source.title} : {source.url}" for source in search_results)


def format_search_results(search_results: List[SearchResult]) -> str:
    formatted_text = "Sources:\n\n"
    for _, source in enumerate(search_results):
        formatted_text += f"Source: {source.title}\n===\n"
        formatted_text += f"URL: {source.url}\n===\n"
        formatted_text += (
            f"Most relevant content from source: {source.description}\n===\n"
        )

    return formatted_text.strip()


def strip_thinking_tokens(text: str) -> str:
    while "<think>" in text and "</think>" in text:
        start = text.find("<think>")
        end = text.find("</think>") + len("</think>")
        text = text[:start] + text[end:]
    return text


@dataclass(kw_only=True)
class SummaryState:
    research_topic: str = field(default=None)  # Report topic
    search_query: str = field(default=None)  # Search query
    web_research_results: Annotated[list, operator.add] = field(default_factory=list)
    sources_gathered: Annotated[list, operator.add] = field(default_factory=list)
    research_loop_count: int = field(default=0)  # Research loop count
    running_summary: str = field(default=None)  # Final report


@dataclass(kw_only=True)
class SummaryStateInput:
    research_topic: str = field(default=None)  # Report topic


@dataclass(kw_only=True)
class SummaryStateOutput:
    running_summary: str = field(default=None)  # Final report


class DeepResearchAgent:
    def __init__(self, search_engine: SearchEngine = None):
        self.search_engine = search_engine or SearchEngine()
        self.max_web_research_loops = 5
        self.llm_config = {
            "model": os.getenv("CHAT_MODEL_NAME"),
            "api_key": os.getenv("CHAT_MODEL_API_KEY"),
            "api_base": os.getenv("CHAT_MODEL_BASE_URL"),
            "timeout": 600,
        }
        self.state = SummaryState()

    async def generate_query(self):
        current_date = get_current_date()
        formatted_prompt = QUERY_WRITER_INSTRUCTIONS.format(
            current_date=current_date, research_topic=self.state.research_topic
        )
        result = await execute_completion_async(
            system=formatted_prompt,
            prompt="Generate a query for web search:",
            response_model=dict,
            llm_config=self.llm_config,
        )
        content = result.text
        try:
            query = json.loads(content)
            search_query = query["query"]
        except (json.JSONDecodeError, KeyError):
            content = strip_thinking_tokens(content)
            search_query = content
        self.state.search_query = search_query

    async def web_research(self):
        search_results = await self.search_engine.search_async(self.state.search_query)
        self.state.sources_gathered = [format_sources(search_results)]
        self.state.research_loop_count += 1
        self.state.web_research_results = [format_search_results(search_results)]

    async def summarize_sources(self):
        existing_summary = self.state.running_summary
        most_recent_web_research = self.state.web_research_results[-1]
        if existing_summary:
            human_message_content = (
                f"<Existing Summary> \n {existing_summary} \n <Existing Summary>\n\n"
                f"<New Context> \n {most_recent_web_research} \n <New Context>"
                f"Update the Existing Summary with the New Context on this topic: \n <User Input> \n {self.state.research_topic} \n <User Input>\n\n"
            )
        else:
            human_message_content = (
                f"<Context> \n {most_recent_web_research} \n <Context>"
                f"Create a Summary using the Context on this topic: \n <User Input> \n {self.state.research_topic} \n <User Input>\n\n"
            )
        response = await execute_completion_async(
            SUMMARIZER_INSTRUCTIONS, human_message_content, llm_config=self.llm_config
        )

        running_summary = response.text
        # if self.config.strip_thinking_tokens:
        if True:
            running_summary = strip_thinking_tokens(running_summary)
        self.state.running_summary = running_summary

    async def reflect_on_summary(self):
        response = await execute_completion_async(
            REFLECTION_INSTRUCTIONS.format(research_topic=self.state.research_topic),
            f"Reflect on our existing knowledge: \n === \n {self.state.running_summary}, \n === \n And now identify a knowledge gap and generate a follow-up web search query:",
            llm_config=self.llm_config,
        )
        try:
            response_text: str = str(response.text).strip()
            if response_text.startswith("```json"):
                response_text = response_text.strip("```json").strip("```").strip()
            reflection_content: dict = json.loads(response_text)
            query = reflection_content.get("follow_up_query")
            if not query:
                self.state.search_query = (
                    f"Tell me more about {self.state.research_topic}"
                )
                # self.state.search_query = None
                # self.state.research_loop_count = self.max_web_research_loops
            else:
                self.state.search_query = query
        except (json.JSONDecodeError, KeyError, AttributeError):
            self.state.search_query = f"Tell me more about {self.state.research_topic}"

    def finalize_summary(self):
        seen_sources = set()
        unique_sources = []
        for source in self.state.sources_gathered:
            for line in source.split("\n"):
                if line.strip() and line not in seen_sources:
                    seen_sources.add(line)
                    unique_sources.append(line)
        all_sources = "\n".join(unique_sources)
        self.state.running_summary = (
            f"## Summary\n{self.state.running_summary}\n\n ### Sources:\n{all_sources}"
        )
        logger.info(f"Final Summary: {self.state.running_summary}")

    async def run(
        self,
        research_topic,
        max_loop_count=5,
        queue: Optional[asyncio.Queue[str]] = None,
    ):
        try:
            self.max_web_research_loops = max_loop_count
            self.state.research_topic = research_topic
            await self.generate_query()
            if queue:
                await queue.put(self.state.search_query)
            while self.state.research_loop_count <= self.max_web_research_loops:
                await self.web_research()
                if queue:
                    await queue.put(self.state.sources_gathered)
                await self.summarize_sources()
                if queue:
                    await queue.put(self.state.running_summary)
                await self.reflect_on_summary()
                if queue:
                    await queue.put(self.state.search_query)
            self.finalize_summary()
            await queue.put(self.state.running_summary)
        except Exception as e:
            logger.error(f"DeepResearchAgent run error: {e}")
            if queue:
                await queue.put(f"DeepResearchAgent run error: {e}")
        if queue:
            await queue.put(TASK_DONE)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    agent = DeepResearchAgent()
    result = asyncio.run(
        agent.run(
            research_topic="What are the latest developments in AI?",
            max_loop_count=5,
        )
    )
    print(result)
