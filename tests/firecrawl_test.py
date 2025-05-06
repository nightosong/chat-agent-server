import pytest
from unittest.mock import patch, MagicMock
from modules.toolkits.firecrawl_serve import FirecrawlService


@pytest.fixture
def firecrawl_service() -> FirecrawlService:
    return FirecrawlService(api_url="http://fake-api/firecrawl")


def test_scrape_success(firecrawl_service: FirecrawlService):
    fake_response = {"content": "some markdown content"}

    with patch.object(
        firecrawl_service.app, "scrape_url", return_value=fake_response
    ) as mock_scrape:
        result = firecrawl_service.scrape("https://example.com")

        mock_scrape.assert_called_once()
        assert result == fake_response


def test_crawl_success(firecrawl_service: FirecrawlService):
    fake_response = {"results": ["page1", "page2"]}

    with patch.object(
        firecrawl_service.app, "crawl_url", return_value=fake_response
    ) as mock_crawl:
        result = firecrawl_service.crawl("https://example.com")

        mock_crawl.assert_called_once()
        assert result == fake_response
