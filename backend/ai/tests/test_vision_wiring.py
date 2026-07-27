def test_anthropic_vision_module_removed():
    import importlib
    try:
        importlib.import_module("app.llm.anthropic_vision")
    except ModuleNotFoundError:
        return
    raise AssertionError("anthropic_vision 모듈이 아직 존재한다 — Gemini로 대체되어야 함")


def test_build_analyzer_stub_via_settings(monkeypatch):
    from app.core.config import settings
    from app.services.vision_analyzer import StubVisionAnalyzer, build_analyzer
    monkeypatch.setattr(settings, "vision_provider", "stub", raising=False)
    assert isinstance(build_analyzer(settings), StubVisionAnalyzer)
