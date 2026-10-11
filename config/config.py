import os
from dotenv import load_dotenv

# Load environment variables using app utils if available, fallback to dotenv
try:
    from app.utils.paths import load_environment
    load_environment()
except ImportError:
    load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY")
