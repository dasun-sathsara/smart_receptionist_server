import logging
import os

from dotenv import load_dotenv
from rich.logging import RichHandler

# Load environment variables from .env file
load_dotenv()

# Set up logging with RichHandler
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],  # Enable rich tracebacks for errors
)

# Set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)


class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
    SINRIC_APP_KEY = os.getenv("SINRIC_APP_KEY")
    SINRIC_APP_SECRET = os.getenv("SINRIC_APP_SECRET")
    GATE_ID = os.getenv("GATE_ID")
    LIGHT_ID = os.getenv("LIGHT_ID")

    SAMPLE_RATE = 44100
    BYTES_PER_SAMPLE = 2
    DEFAULT_CHUNK_SIZE = 1024

    @staticmethod
    def validate():
        if not Config.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is not set in the environment variables")
        if not Config.ADMIN_USER_ID:
            raise ValueError("ADMIN_USER_ID is not set in the environment variables")
        if not Config.SINRIC_APP_KEY:
            raise ValueError("SINRIC_APP_KEY is not set in the environment variables")
        if not Config.SINRIC_APP_SECRET:
            raise ValueError("SINRIC_APP_SECRET is not set in the environment variables")
        if not Config.GATE_ID:
            raise ValueError("GATE_ID is not set in the environment variables")
        if not Config.LIGHT_ID:
            raise ValueError("LIGHT_ID is not set in the environment variables")
