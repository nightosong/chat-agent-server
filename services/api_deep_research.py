import asyncio
from fastapi import APIRouter, BackgroundTasks, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agents.deep_research_v2 import DeepResearchAgent, TASK_DONE

router = APIRouter(prefix="/api", tags=["deep_research"])
agent = DeepResearchAgent()


class ResearchRequest(BaseModel):
    query: str
    breadth: int = 4
    depth: int = 2
    is_report: bool = True


@router.post("/deep_research")
async def deep_research_api(request: ResearchRequest):
    async def event_generator():
        query = request.query
        breadth = request.breadth
        depth = request.depth
        is_report = request.is_report
        queue = asyncio.Queue()
        task = asyncio.create_task(agent.run(query, breadth, depth, is_report, queue))
        while True:
            msg = await asyncio.wait_for(queue.get(), timeout=600)
            if msg == TASK_DONE:
                break
            yield f"data: {msg}\n\n"
        await task
        yield f"data: {task}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
