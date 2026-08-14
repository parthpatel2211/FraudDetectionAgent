import importlib


def test_api_key_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import backend.config as config
    importlib.reload(config)
    assert config.settings.ANTHROPIC_API_KEY == "sk-ant-test"


def test_api_key_absent_is_none(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import backend.config as config
    importlib.reload(config)
    assert config.settings.ANTHROPIC_API_KEY is None


def test_allowed_origins_parses_csv(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.dev, https://b.dev")
    import backend.config as config
    importlib.reload(config)
    assert config.settings.ALLOWED_ORIGINS == ["https://a.dev", "https://b.dev"]


def test_allowed_origins_empty_is_empty_list(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "")
    import backend.config as config
    importlib.reload(config)
    assert config.settings.ALLOWED_ORIGINS == []


def test_numeric_settings_are_coerced(monkeypatch):
    monkeypatch.setenv("RISK_THRESHOLD", "0.65")
    monkeypatch.setenv("MAX_TRANSACTIONS_PER_REQUEST", "123")
    import backend.config as config
    importlib.reload(config)
    assert config.settings.RISK_THRESHOLD == 0.65
    assert config.settings.MAX_TRANSACTIONS_PER_REQUEST == 123
