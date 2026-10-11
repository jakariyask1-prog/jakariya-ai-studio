import os

from app.utils.paths import load_environment

load_environment()

try:
    from tavily import TavilyClient
except ImportError as exc:
    raise RuntimeError(
        "The 'tavily' package is required. Install it with 'pip install tavily-python'."
    ) from exc


class WebSearch:
    """
    Tavily Web Search Client
    """

    def __init__(self):
        api_key = os.getenv("TAVILY_API_KEY")

        if not api_key:
            raise RuntimeError(
                "TAVILY_API_KEY was not found in your .env file."
            )

        self.client = TavilyClient(api_key=api_key)

    def search(self, query: str, max_results: int = 5) -> dict:
        """
        Search the web using Tavily.
        """

        return self.client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_answer=True,
            include_raw_content=False,
            include_images=False,
        )