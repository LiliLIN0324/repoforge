from repoforge.config import Settings


def test_defaults_use_mock_without_key(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.setenv("REPOFORGE_DRY_RUN", "1")
    s = Settings()
    assert s.use_mock is True
    assert "tokenfactory.nebius.com" in s.nebius_base_url


def test_model_for_tiers():
    s = Settings()
    assert "Nano" in s.model_for("nano") or "nano" in s.model_for("nano").lower()
    assert "super" in s.model_for("super").lower()
    assert "Ultra" in s.model_for("ultra") or "ultra" in s.model_for("ultra").lower()
