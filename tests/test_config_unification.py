from app.config import Config


def test_config_exposes_unified_backend_env_keys():
    expected = {
        "NVIDIA_API_KEY",
        "APIFY_TOKEN",
        "TAVILY_API_KEY",
        "YOUTUBE_API_KEY",
        "DEEPGRAM_API_KEY",
        "PAYSTACK_SECRET_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "DATABASE_URL",
        "ZEP_API_KEY",
        "LLM_BOOST_API_KEY",
        "LLM_BOOST_BASE_URL",
        "LLM_BOOST_MODEL_NAME",
    }

    missing = sorted(key for key in expected if not hasattr(Config, key))
    assert not missing, f"Config missing expected env keys: {missing}"


def test_config_validate_does_not_block_optional_services():
    issues = Config.validate()
    assert isinstance(issues, list)
