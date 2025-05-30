import asyncio
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from modules.ai.llms import execute_intention_reference_async
from modules.search.firecrawl_engine import FirecrawlEngine
from modules.search.searxng_engine import SearxngEngine
from modules.search.playwright_engine import PlaywrightEngine
from agents.deep_research_v2 import DeepResearchAgent as AgentV2, TASK_DONE
from agents.deep_research_v3 import DeepResearchAgent as AgentV3

router = APIRouter(prefix="/api", tags=["deep_research"])
search_engine = SearxngEngine()
agent_v2 = AgentV2(search_engine)
agent_v3 = AgentV3(search_engine)


def create_search_engine(
    engine: Literal["searxng", "playwright", "firecrawl"] = "searxng"
):
    if engine == "searxng":
        return SearxngEngine()
    elif engine == "firecrawl":
        return FirecrawlEngine()
    else:
        return PlaywrightEngine()


class ResearchRequest(BaseModel):
    query: str
    breadth: int = 4
    depth: int = 2
    is_report: bool = True
    engine: Literal["searxng", "playwright", "firecrawl"] = "searxng"


@router.post("/deep_research")
async def deep_research_api(request: ResearchRequest):
    async def event_generator():
        query = request.query
        breadth = request.breadth
        depth = request.depth
        is_report = request.is_report
        queue = asyncio.Queue()
        engine = create_search_engine(request.engine)
        intention = await execute_intention_reference_async(query, int)
        if intention == 2:
            task = asyncio.create_task(
                AgentV2(engine).run(query, breadth, depth, is_report, queue)
            )
        else:
            task = asyncio.create_task(AgentV3(engine).run(query, depth, queue))
        while True:
            msg = await asyncio.wait_for(queue.get(), timeout=600)
            if msg == TASK_DONE:
                break
            yield f"data: {msg}\n\n"
        await task
        yield f"data: {task}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
