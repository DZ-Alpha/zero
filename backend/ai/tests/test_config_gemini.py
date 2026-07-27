from app.core.config import settings


def test_gemini_settings_have_defaults():
    assert settings.gemini_model == "gemini-flash-latest"
    assert settings.gemini_thinking_budget == 512
    assert settings.gemini_max_output_tokens == 4096
    assert settings.vision_provider == "gemini"
    assert settings.vision_timeout_seconds == 30.0
    assert settings.vision_confidence_threshold == 0.75
    assert isinstance(settings.gemini_api_key, str)
