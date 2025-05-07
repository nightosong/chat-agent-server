import time
import requests
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from lxml import html
from firecrawl.firecrawl import SearchResponse
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
from modules.loggers import logger

load_dotenv()


class SearchResult(BaseModel):
    title: str = Field(description="The title of the search result")
    description: str = Field(description="The description of the search result")
    url: str = Field(description="The URL of the search result")


class FirecrawlMock:
    def bing_search(
        self,
        term: str,
        num_results: int = 5,
        lang: str = "en",
        country: str = "us",
        proxy: str = None,
        sleep_interval: float = 0,
        timeout: int = 15,
    ) -> SearchResponse:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "*/*",
        }

        proxies = {"http": proxy, "https": proxy} if proxy else None

        start = 0
        results = []
        attempts = 0
        max_attempts = 10

        while start < num_results and attempts < max_attempts:
            try:
                params = {
                    "q": term,
                    "count": num_results - start,
                    "offset": start,
                    "mkt": f"{lang}-{country}",
                }

                resp = requests.get(
                    "https://cn.bing.com/search",
                    headers=headers,
                    params=params,
                    proxies=proxies,
                    timeout=timeout,
                )

                if resp.status_code == 429:
                    logger.warning("Bing Search: Too many requests")
                    break

                tree = html.fromstring(resp.text)
                blocks = tree.xpath('//li[contains(@class, "b_algo")]')

                if not blocks:
                    attempts += 1
                    start += 1
                    continue

                for block in blocks:
                    title_elem = block.xpath(".//h2/a")
                    desc_elem = block.xpath('.//div[contains(@class, "b_caption")]/p')

                    if title_elem and desc_elem:
                        title = title_elem[0].text_content().strip()
                        link = title_elem[0].get("href")
                        desc = desc_elem[0].text_content().strip()

                        if link and title and desc:
                            results.append(
                                SearchResult(title=title, description=desc, url=link)
                            )
                            start += 1

                        if len(results) >= num_results:
                            break

                time.sleep(sleep_interval)

            except Exception as e:
                logger.error(f"Error during Bing search: {e}")
                break
        response = SearchResponse(success=True, data=results)
        return response

    def bing_search_playwright(
        self,
        query: str,
        num_results: int = 5,
        lang: str = "en",
        country: str = "us",
        proxy: str = None,
        sleep_interval: float = 0,
        timeout: int = 15,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=False)
            page = browser.new_page()

            page.goto(
                f"https://www.bing.com/search?q={query}",
                wait_until="domcontentloaded",
                timeout=timeout * 1000,
            )
            page.wait_for_selector("li.b_algo")
            items = page.query_selector_all("li.b_algo")

            results = []
            for item in items:
                title_elem = item.query_selector("h2 a")
                desc_elem = item.query_selector(".b_caption p")
                if title_elem and desc_elem:
                    title = title_elem.inner_text()
                    link = title_elem.get_attribute("href")
                    desc = desc_elem.inner_text()
                    results.append({"title": title, "url": link, "description": desc})
            browser.close()
        return results

    async def bing_search_playwright_async(
        self,
        query: str,
        num_results: int = 5,
        lang: str = "en",
        country: str = "us",
        proxy: str = None,
        sleep_interval: float = 0,
        timeout: int = 15,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        results = []
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=False)
            page = await browser.new_page()
            await page.goto(
                f"https://www.bing.com/search?q={query}",
                wait_until="networkidle",
                timeout=timeout * 1000,
            )
            await page.wait_for_timeout(1000)
            try:
                await page.wait_for_selector("li.b_algo", timeout=60000)
            except TimeoutError:
                logger.error("查找选择器 'li.b_algo' 超时")
                await browser.close()
                return []

            items = await page.query_selector_all("li.b_algo")
            for item in items[:num_results]:
                title_elem = await item.query_selector("h2 a")
                desc_elem = await item.query_selector(".b_caption p")
                if title_elem and desc_elem:
                    title = await title_elem.inner_text()
                    link = await title_elem.get_attribute("href")
                    desc = await desc_elem.inner_text()
                    results.append({"title": title, "url": link, "description": desc})

            await browser.close()
        return results

    def search(self, query: str, params=None):
        if not params:
            params = {"num_results": 5, "lang": "en", "country": "us"}
        response = self.bing_search_playwright(query, **params)
        return SearchResponse(success=True, data=response)

    async def search_async(self, query, params=None):
        if not params:
            params = {"num_results": 5, "lang": "en", "country": "us"}
        response = await self.bing_search_playwright_async(query, **params)
        return SearchResponse(success=True, data=response)


if __name__ == "__main__":
    # results = FirecrawlMock().search("2025-2030 AI颠覆性技术路线图")
    results = FirecrawlMock().search("2025-2030 AI颠覆性技术路线图")
    print(results)
