import os
import aiohttp
import requests
from typing import List, override
from modules.search.base_engine import SearchEngine, SearchResult


class SearxngEngine(SearchEngine):
    def __init__(self):
        self.base_url = os.getenv("SEARXNG_SERVE_URL")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "*/*",
        }
        self.timeout = 120

    @override
    def search(
        self, query: str, num_results: int = 100, **kwargs
    ) -> List[SearchResult]:
        params = {
            "q": query,
            "categories": "general",
            "language": "zh-CN",
            "safesearch": "0",
            "time_range": "month",
            "format": "json",
        }
        response = requests.get(
            f"{self.base_url}/search",
            params=params,
            headers=self.headers,
            timeout=self.timeout,
        )
        if response.status_code == 200:
            results = response.json()["results"]
            return [
                SearchResult(
                    title=result["title"],
                    description=result["content"],
                    url=result["url"],
                )
                for result in results[:num_results]
            ]
        else:
            return []

    @override
    async def search_async(
        self, query: str, num_results: int = 100, **kwargs
    ) -> List[SearchResult]:
        params = {
            "q": query,
            "categories": "general",
            "language": "zh-CN",
            "safesearch": "0",
            "time_range": "month",
            "format": "json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/search",
                params=params,
                headers=self.headers,
                timeout=self.timeout,
            ) as response:
                if response.status == 200:
                    results = await response.json()
                    return [
                        SearchResult(
                            title=result["title"],
                            description=result["content"],
                            url=result["url"],
                        )
                        for result in results["results"][:num_results]
                    ]
                else:
                    return []


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv

    load_dotenv()
    searxng_serve = SearxngEngine()
    results = searxng_serve.search("chatgpt", num_results=5)
    print(results)
    results = asyncio.run(searxng_serve.search_async("chatgpt", num_results=5))
    print(results)
