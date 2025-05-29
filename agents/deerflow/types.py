import operator
from enum import Enum
from typing import Annotated, Optional
from pydantic import BaseModel, Field
from langgraph.graph import MessagesState


class StepType(str, Enum):
    RESEARCH = "research"
    PROCESSING = "processing"


class Step(BaseModel):
    need_web_search: bool = Field(
        ..., description="Must be explicitly set for each step"
    )
    title: str
    description: str = Field(..., description="Specify exactly what data to collect")
    step_type: StepType = Field(..., description="Indicates the nature of the step")
    execution_res: str | None = Field(
        default=None, description="The Step execution result"
    )


class Plan(BaseModel):
    local: str = Field(
        ..., description="e.g. 'zh-CN' or 'en-US', based on the user's language."
    )
    has_enough_context: bool
    thought: str
    title: str
    steps: list[Step] = Field(
        default_factory=list,
        description="Research & Processing steps to get more context",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "has_enough_context": False,
                    "thought": (
                        "To understand the current market trends in AI, we need to gather comprehensive information."
                    ),
                    "title": "AI Market Research Plan",
                    "steps": [
                        {
                            "need_web_search": True,
                            "title": "Current AI Market Analysis",
                            "description": (
                                "Collect data on market size, growth rates, major players, and investment trends in AI sector."
                            ),
                            "step_type": "research",
                        }
                    ],
                }
            ]
        }


class State(MessagesState):
    """State for the agent system."""

    local: str = "zh-CN"
    observations: list[str] = []
    plan_iterations: int = 0
    current_plan: Plan | str = None
    final_report: str = ""
    auto_accepted_plan: bool = False
    enable_background_investigation: bool = True
    background_investigation_results: str = None
