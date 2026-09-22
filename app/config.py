"""Central backend configuration loader.

This keeps the app using one shared source of truth for both Flask and AI
service environment variables.
"""

import os
from dotenv import load_dotenv


def _load_project_env_files():
    """Load local project env files in a predictable order."""
    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    candidates = [
        os.path.join(project_dir, '.env'),
        os.path.join(project_dir, '.env.local'),
        os.path.join(project_dir, '..', '.env'),
    ]

    for env_path in candidates:
        if os.path.exists(env_path):
            load_dotenv(env_path, override=False)

    load_dotenv(override=False)


_load_project_env_files()


class Config:
    """Shared backend configuration."""

    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    JSON_AS_ASCII = False

    NVIDIA_API_KEY = os.environ.get('NVIDIA_API_KEY')
    NVIDIA_BASE_URL = os.environ.get('NVIDIA_BASE_URL', 'https://integrate.api.nvidia.com/v1')
    NVIDIA_MODEL_NAME = os.environ.get('NVIDIA_MODEL_NAME', 'nvidia/nemotron-3-super-120b-a12b')

    APIFY_TOKEN = os.environ.get('APIFY_TOKEN')
    DEEPGRAM_API_KEY = os.environ.get('DEEPGRAM_API_KEY')
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY')

    DATABASE_URL = os.environ.get('DATABASE_URL')

    TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY')
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')

    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')
    LLM_BOOST_API_KEY = os.environ.get('LLM_BOOST_API_KEY')
    LLM_BOOST_BASE_URL = os.environ.get('LLM_BOOST_BASE_URL')
    LLM_BOOST_MODEL_NAME = os.environ.get('LLM_BOOST_MODEL_NAME')

    LLM_API_KEY = NVIDIA_API_KEY
    LLM_BASE_URL = NVIDIA_BASE_URL
    LLM_MODEL_NAME = NVIDIA_MODEL_NAME

    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}

    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_CHUNK_OVERLAP = 50

    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')

    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]

    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    @classmethod
    def validate(cls):
        """Validate required config entries."""
        errors = []

        if not cls.NVIDIA_API_KEY and not cls.LLM_API_KEY:
            errors.append("NVIDIA_API_KEY is not configured")

        if not cls.APIFY_TOKEN:
            errors.append("APIFY_TOKEN is not configured")

        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL is not configured (PostgreSQL)")

        return errors


