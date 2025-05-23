import os
import urllib.parse
from typing import List, override

from firecrawl.firecrawl import FirecrawlApp, AsyncFirecrawlApp, ScrapeOptions
from modules.loggers import logger
from modules.web.base_engine import SearchResult, SearchEngine


class FirecrawlEngine(SearchEngine):
    def __init__(self, https_proxy=None):
        self.api_url = os.getenv("FIRECRAWL_BASE_URL")
        self.https_proxy = https_proxy
        self.app = FirecrawlApp(api_url=self.api_url)
        self.app_async = AsyncFirecrawlApp(api_url=self.api_url)

    def scrape(self, url, params=None):
        """爬取网址"""
        if not params:
            params = {"formats": ["markdown"]}
        scrape_result = self.app.scrape_url(url, **params)
        return scrape_result

    async def scrape_async(self, url, params=None):
        """异步爬取网址"""
        if not params:
            params = {"formats": ["markdown"]}
        scrape_result = await self.app_async.scrape_url(url, **params)
        return scrape_result

    def crawl(self, url, params=None):
        """爬取网址"""
        if not params:
            params = {
                "limit": 10,
                "scrape_options": {"formats": ["markdown"]},
                "poll_interval": 30,
            }
        params["scrape_options"] = ScrapeOptions(**params["scrape_options"])
        crawl_result = self.app.crawl_url(url, **params)
        return crawl_result

    async def crawl_async(self, url, params=None):
        """异步爬取网址"""
        if not params:
            params = {
                "limit": 10,
                "scrape_options": {"formats": ["markdown"]},
                "poll_interval": 30,
            }
        params["scrape_options"] = ScrapeOptions(**params["scrape_options"])

        crawl_result = await self.app_async.crawl_url(url, **params)
        return crawl_result

    def bing_search(self, query, params=None):
        # search_url = f"https://www.baidu.com/s?wd={query}"
        query = urllib.parse.quote(query)
        search_url = f"https://cn.bing.com/search?q={query}"
        return self.crawl(search_url)

    async def bing_search_async(self, query, params=None):
        search_url = f"https://cn.bing.com/search?q={query}"
        logger.info(f"search url: {search_url}")
        return await self.crawl_async(search_url)

    @override
    def search(self, query: str, params=None) -> List[SearchResult]:
        """搜索"""
        if not params:
            params = {
                "limit": 5,
                "scrape_options": {"formats": ["markdown"]},
                "timeout": 15000,
            }
        params["scrape_options"] = ScrapeOptions(**params["scrape_options"])
        response = self.app.search(query, **params)
        if response.success:
            return [SearchResult(**result) for result in response.data]
        return []

    @override
    async def search_async(self, query, params=None) -> List[SearchResult]:
        """异步搜索"""
        if not params:
            params = {
                "limit": 5,
                "scrape_options": {"formats": ["markdown"]},
                "timeout": 15000,
            }
        params["scrape_options"] = ScrapeOptions(**params["scrape_options"])
        response = await self.app_async.search(query, **params)
        if response.success:
            return [SearchResult(**result) for result in response.data]
        return []

    def extract(self, urls, params=None):
        response = self.app.extract(urls, **params)
        return response

    async def extract_async(self, urls, params=None):
        response = await self.app_async.async_extract(urls, **params)
        return response


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    engine = FirecrawlEngine()
    result = engine.search("python")
    print(result)
