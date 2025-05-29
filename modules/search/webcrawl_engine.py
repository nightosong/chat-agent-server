import os
import json
from typing import List
from firecrawl import FirecrawlApp
from modules.ai.llms import execute_completion, execute_completion_async
from modules.loggers import logger
from modules.search.base_engine import SearchResult, SearchEngine

# region 配置提示词
MAP_PROMPT = """
The map function generates a list of URLs from a website and it accepts a search parameter. Based on the objective of: {objective}, come up with a 1-2 word search parameter that will help us find the information we need. Only respond with 1-2 words nothing else.
"""
RANK_PROMPT = """
Given the following list of URLs and the stated objective: {objective}
URLs to analyze:
{urls}

Your task is to:

1. Analyze the content and likely relevance of each URL based on the objective.
2. Choose the 3 most relevant URLs, even if the relevance is low — **you must always select 3**.
3. For each selected URL, provide:
    - "url": the full URL
    - "relevance_score": an integer between 0-100 (where 100 means perfectly relevant)
    - "reason": a short, clear justification for the relevance score.

Scoring guidelines:
- If a URL is highly related to the objective, assign a score close to 100.
- If a URL is only loosely related, assign a lower score (e.g., 50-70), but still include it if better options are unavailable.
- If no URL seems highly relevant, still pick the best 3 candidates available and score them appropriately.

Format:
Return your response as a **valid JSON array** with exactly 3 objects, no more, no fewer.
Do not return an empty array. Do not skip the task even if relevance is low.

Example output:
[
    {{
        "url": "https://example.com/about",
        "relevance_score": 95,
        "reason": "Main about page containing company information"
    }},
    {{
        "url": "https://example.com/team",
        "relevance_score": 80,
        "reason": "Team page with leadership details"
    }},
    {{
        "url": "https://example.com/contact",
        "relevance_score": 70,
        "reason": "Contact page with location information"
    }}
]

"""
CHECK_PROMPT = """
Given the following scraped content and objective, determine if the objective is met.
If it is, extract the relevant information in a simple and concise JSON format. Use only the necessary fields and avoid nested structures if possible.
If the objective is not met with confidence, respond with exactly 'Objective not met'.

The JSON format should be:
{{
    "found": true,
    "data": {{
        // extracted information here
    }}
}}

Important: Do not wrap the JSON in markdown code blocks. Just return the raw JSON.

Objective: {objective}
Scraped content: {scrape_result}

Remember:
1. Only return JSON if you are confident the objective is fully met.
2. Keep the JSON structure as simple and flat as possible.
3. If returning JSON, ensure it's valid JSON format without any markdown formatting.
4. If objective is not met, respond only with 'Objective not met'.
"""
# endregion


class Colors:
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


class WebCrawlEngine(SearchEngine):
    def __init__(self):
        # Retrieve API keys from environment variables
        self.firecrawl_base_url = os.getenv("FIRECRAWL_BASE_URL")
        self.claude_api_key = os.getenv("ANTHROPIC_API_KEY")

        # Initialize the FirecrawlApp and Claude client
        self.app = FirecrawlApp(api_url=self.firecrawl_base_url)
        self.llm_config = {
            "model": os.getenv("CHAT_MODEL_NAME"),
            "api_key": os.getenv("CHAT_MODEL_API_KEY"),
            "api_base": os.getenv("CHAT_MODEL_BASE_URL"),
        }

    # Find the page that most likely contains the objective
    def find_relevant_page_via_map(self, objective, url):
        try:
            logger.info(
                f"{Colors.CYAN}Understood. The objective is: {objective}{Colors.RESET}"
            )
            logger.info(
                f"{Colors.CYAN}Initiating search on the website: {url}{Colors.RESET}"
            )

            map_prompt = MAP_PROMPT.format(objective=objective)

            logger.info(
                f"{Colors.YELLOW}Analyzing objective to determine optimal search parameter...{Colors.RESET}"
            )
            completion = execute_completion(
                prompt=map_prompt,
                response_model=dict,
                llm_config=self.llm_config,
            )
            print(completion.text)

            map_search_parameter: str = completion.text
            logger.info(
                f"{Colors.GREEN}Optimal search parameter identified: {map_search_parameter}{Colors.RESET}"
            )

            logger.info(
                f"{Colors.YELLOW}Mapping website using the identified search parameter...{Colors.RESET}"
            )
            map_website = self.app.map_url(url, search=map_search_parameter.strip())

            # Debug logger.info to see the response structure
            logger.info(
                f"{Colors.MAGENTA}Debug - Map response structure: {map_website.model_dump_json()}{Colors.RESET}"
            )

            logger.info(
                f"{Colors.GREEN}Website mapping completed successfully.{Colors.RESET}"
            )

            links = map_website.links

            if not links:
                logger.info(
                    f"{Colors.RED}No links found in map response.{Colors.RESET}"
                )
                return None

            rank_prompt = RANK_PROMPT.format(
                objective=objective, urls=json.dumps(links, indent=2)
            )

            logger.info(
                f"{Colors.YELLOW}Ranking URLs by relevance to objective...{Colors.RESET}"
            )
            completion = execute_completion(
                prompt=rank_prompt,
                response_model=dict,
                llm_config=self.llm_config,
            )
            print("#", completion.text, "#")

            # Debug logger.info to see Claude's raw response
            logger.info(f"{Colors.MAGENTA}Debug - Claude's raw response:{Colors.RESET}")
            logger.info(f"{Colors.MAGENTA}{completion.text}{Colors.RESET}")

            try:
                # Try to clean the response by stripping any potential markdown or extra whitespace
                cleaned_response: str = completion.text.strip()
                if cleaned_response.startswith("```json"):
                    cleaned_response = cleaned_response.split("```json")[1]
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response.rsplit("```", 1)[0]
                cleaned_response = cleaned_response.strip()

                ranked_results = json.loads(cleaned_response)

                # Validate the structure of the results
                if not isinstance(ranked_results, list):
                    raise ValueError("Response is not a list")

                for result in ranked_results:
                    if not all(
                        key in result for key in ["url", "relevance_score", "reason"]
                    ):
                        raise ValueError("Response items missing required fields")

                links = [result["url"] for result in ranked_results]

                # logger.info detailed ranking info
                logger.info(f"{Colors.CYAN}Top 3 ranked URLs:{Colors.RESET}")
                for result in ranked_results:
                    logger.info(f"{Colors.GREEN}URL: {result['url']}{Colors.RESET}")
                    logger.info(
                        f"{Colors.YELLOW}Relevance Score: {result['relevance_score']}{Colors.RESET}"
                    )
                    logger.info(
                        f"{Colors.BLUE}Reason: {result['reason']}{Colors.RESET}"
                    )
                    logger.info("---")

                if not links:
                    logger.info(
                        f"{Colors.RED}No relevant links identified.{Colors.RESET}"
                    )
                    return None

            except (json.JSONDecodeError, KeyError) as e:
                logger.info(
                    f"{Colors.RED}Error parsing ranked results: {str(e)}{Colors.RESET}"
                )
                return None

            logger.info(
                f"{Colors.GREEN}Located {len(links)} relevant links.{Colors.RESET}"
            )
            return links

        except Exception as e:
            logger.info(
                f"{Colors.RED}Error encountered during relevant page identification: {str(e)}{Colors.RESET}"
            )
            return None

    # Scrape the top 3 pages and see if the objective is met, if so return in json format else return None
    def find_objective_in_top_pages(self, map_website, objective):
        try:
            # Get top 3 links from the map result
            if not map_website:
                logger.info(f"{Colors.RED}No links found to analyze.{Colors.RESET}")
                return None

            top_links = map_website[:3]
            logger.info(
                f"{Colors.CYAN}Proceeding to analyze top {len(top_links)} links: {top_links}{Colors.RESET}"
            )

            for link in top_links:
                logger.info(
                    f"{Colors.YELLOW}Initiating scrape of page: {link}{Colors.RESET}"
                )
                scrape_result = self.app.scrape_url(link, formats=["markdown"])
                logger.info(
                    f"{Colors.GREEN}Page scraping completed successfully.{Colors.RESET}"
                )

                check_prompt = CHECK_PROMPT.format(
                    objective=objective, scrape_result=scrape_result["markdown"]
                )

                completion = execute_completion(
                    prompt=check_prompt,
                    response_model=dict,
                    llm_config=self.llm_config,
                )

                result: str = completion.text.strip()

                # Clean up the response if it contains markdown formatting
                if result.startswith("```json"):
                    result = result.split("```json")[1]
                if result.endswith("```"):
                    result = result.rsplit("```", 1)[0]
                result = result.strip()

                if result == "Objective not met":
                    logger.info(
                        f"{Colors.YELLOW}Objective not met on this page. Proceeding to next link...{Colors.RESET}"
                    )
                    continue

                try:
                    json_result = json.loads(result)
                    logger.info(
                        f"{Colors.GREEN}Objective fulfilled. Relevant information found.{Colors.RESET}"
                    )
                    return json_result
                except json.JSONDecodeError as e:
                    logger.info(
                        f"{Colors.RED}Error parsing JSON response: {str(e)}{Colors.RESET}"
                    )
                    logger.info(f"{Colors.MAGENTA}Raw response: {result}{Colors.RESET}")
                    continue

            logger.info(
                f"{Colors.RED}All available pages analyzed. Objective not fulfilled in examined content.{Colors.RESET}"
            )
            return None

        except Exception as e:
            logger.info(
                f"{Colors.RED}Error encountered during page analysis: {str(e)}{Colors.RESET}"
            )
            return None

    def run(self, url: str, objective: str):
        # Get user input
        logger.info(f"{Colors.BLUE}Enter the website to crawl : {Colors.RESET}")
        logger.info(f"{Colors.BLUE}Enter your objective: {Colors.RESET}")

        logger.info(f"{Colors.YELLOW}Initiating web crawling process...{Colors.RESET}")
        # Find the relevant page
        map_website = self.find_relevant_page_via_map(objective, url)

        if map_website:
            logger.info(
                f"{Colors.GREEN}Relevant pages identified. Proceeding with detailed analysis using Claude 3.7...{Colors.RESET}"
            )
            # Find objective in top pages
            result = self.find_objective_in_top_pages(map_website, objective)

            if result:
                logger.info(
                    f"{Colors.GREEN}Objective successfully fulfilled. Extracted information :{Colors.RESET}"
                )
                logger.info(
                    f"{Colors.MAGENTA}{json.dumps(result, indent=2)}{Colors.RESET}"
                )
            else:
                logger.info(
                    f"{Colors.RED}Unable to fulfill the objective with the available content.{Colors.RESET}"
                )
        else:
            logger.info(
                f"{Colors.RED}No relevant pages identified. Consider refining the search parameters or trying a different website.{Colors.RESET}"
            )
            result = []
        return result

    def search(self, query: str, params=None, **kwargs) -> List[SearchResult]:
        raise NotImplementedError

    async def search_async(self, query: str, params=None, **kwargs):
        raise NotImplementedError


if __name__ == "__main__":
    url = "https://www.chinanews.com.cn/"
    objective = "查找下中国最近的新闻或者外交政策"
    crawler = WebCrawlEngine()
    crawler.run(url, objective)
