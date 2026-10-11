"""Coverage for configured web-search providers used by the AI agent."""

from app.agent.tools.web_search_tool import WebSearchTool


class _FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "web": {
                "results": [
                    {
                        "title": "Current result",
                        "description": "A current result from Brave.",
                        "url": "https://example.com/current",
                    }
                ]
            }
        }


class _FakeHttpClient:
    def __init__(self):
        self.request = None

    def get(self, url, params, headers):
        self.request = (url, params, headers)
        return _FakeResponse()


def test_brave_search_formats_results_and_uses_subscription_token():
    tool = WebSearchTool()
    fake_client = _FakeHttpClient()
    tool._http_client = fake_client

    output = tool._search_brave("latest AI news", "brave-key")

    assert "Current result" in output
    assert "https://example.com/current" in output
    assert fake_client.request[2]["X-Subscription-Token"] == "brave-key"
