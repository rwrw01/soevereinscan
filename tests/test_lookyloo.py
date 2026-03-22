import pytest
from unittest.mock import MagicMock, patch
from app.services.lookyloo_client import LookylooClient


@patch("app.services.lookyloo_client.Lookyloo")
def test_submit_url_returns_uuid(mock_lookyloo_cls):
    mock_instance = MagicMock()
    mock_instance.submit.return_value = "abc-123-def"
    mock_lookyloo_cls.return_value = mock_instance

    client = LookylooClient(lookyloo_url="http://localhost:5100")
    result = client.submit("https://example.com")

    assert result == "abc-123-def"
    mock_instance.submit.assert_called_once()


@patch("app.services.lookyloo_client.Lookyloo")
def test_classify_third_party(mock_lookyloo_cls):
    client = LookylooClient(lookyloo_url="http://localhost:5100")

    # Same domain = not third party
    assert client.classify_third_party("https://example.com/page", "example.com") is False

    # Subdomain = not third party
    assert client.classify_third_party("https://example.com/page", "cdn.example.com") is False

    # Different domain = third party
    assert client.classify_third_party("https://example.com/page", "google.com") is True
