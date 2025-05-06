import time
import httpx
import requests
import asyncio
import urllib.parse

from firecrawl.firecrawl import FirecrawlApp, AsyncFirecrawlApp, ScrapeOptions
from modules.loggers import logger


class FirecrawlService:
    def __init__(self, api_url, https_proxy=None):
        self.api_url = api_url
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

    def search(self, query: str, params=None):
        """搜索"""
        if not params:
            params = {
                "limit": 5,
                "scrape_options": {"formats": ["markdown"]},
                "timeout": 15000,
            }
        params["scrape_options"] = ScrapeOptions(**params["scrape_options"])
        return self.app.search(query, **params)

    async def search_async(self, query, params=None):
        """异步搜索"""
        if not params:
            params = {
                "limit": 5,
                "scrape_options": {"formats": ["markdown"]},
                "timeout": 15000,
            }
        params["scrape_options"] = ScrapeOptions(**params["scrape_options"])
        print(query)
        return await self.app_async.search(query, **params)

    def extract(self, urls, params=None):
        response = self.app.extract(urls, **params)
        print(response)
        return response

    async def extract_async(self, urls, params=None):
        response = await self.app_async.async_extract(urls, **params)
        print(response)


if __name__ == "__main__":
    api_url = "http://192.168.0.101:3002"
    service = FirecrawlService(api_url=api_url)
    # result = service.search("华为")
    # print(result)
    # result_async = loop.run_until_complete(service.search_async("华为"))
    # print(result_async)
    params = {
        "prompt": "提取页面大致内容。",
        "schema": {
            "title": "NewsSchema",
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "by": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["title", "content"],
        },
    }
    # urls = ["https://cn.bing.com/search?q=%E5%AE%9D%E9%A9%AC%E6%96%B0%E9%97%BB"]
    # service.extract(urls, params)
    url = "https://cn.bing.com/search?q=张杰 周杰伦"
    result = service.scrape(url)
    # result = service.bing_search("张杰 周杰伦")
    print(result)
