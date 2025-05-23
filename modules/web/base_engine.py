import json
import asyncio
from typing import List
from pydantic import BaseModel, Field
from abc import ABC, abstractmethod


class SearchResult(BaseModel):
    title: str = Field(description="The title of the search result")
    description: str = Field(description="The description of the search result")
    url: str = Field(description="The URL of the search result")


class SearchEngine(ABC):
    @abstractmethod
    def search(self, query: str, params=None, **kwargs) -> List[SearchResult]:
        raise NotImplementedError("search method must be implemented")

    @abstractmethod
    async def search_async(
        self, query: str, params=None, **kwargs
    ) -> List[SearchResult]:
        raise NotImplementedError("search_async method must be implemented")
