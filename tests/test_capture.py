import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.capture import CaptureService, CaptureResult


def test_capture_result_defaults():
    result = CaptureResult()
    assert result.hostname_ips == {}
    assert result.all_ips == set()
    assert result.cookies == []
    assert result.error is None


def test_classify_third_party():
    assert CaptureService.classify_third_party("https://example.com/page", "example.com") is False
    assert CaptureService.classify_third_party("https://example.com/page", "cdn.example.com") is False
    assert CaptureService.classify_third_party("https://example.com/page", "google.com") is True
    assert CaptureService.classify_third_party("https://example.com/page", "tracker.facebook.com") is True


@pytest.mark.asyncio
async def test_resolve_hostname():
    service = CaptureService()
    # localhost should resolve
    ips = await service._resolve_hostname("localhost")
    assert "127.0.0.1" in ips


@pytest.mark.asyncio
async def test_resolve_hostname_invalid():
    service = CaptureService()
    ips = await service._resolve_hostname("this-does-not-exist.invalid")
    assert ips == []
