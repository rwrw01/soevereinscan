"""
E2E tests for SoevereinScan — tests from user perspective with Playwright.
Requires: app running on http://localhost:8000 with postgres + redis.
"""
import re

import pytest
from playwright.sync_api import Page, expect


BASE_URL = "http://localhost:8000"


# ===================== HAPPY FLOWS =====================


class TestHomepage:
    """User visits the homepage and sees the scan form."""

    def test_homepage_loads(self, page: Page):
        page.goto(BASE_URL)

        # Page title is Dutch
        expect(page).to_have_title(re.compile("SoevereinScan"))

        # Header visible
        expect(page.locator("header h1")).to_have_text("SoevereinScan")

        # Scan form visible
        expect(page.locator("#scan-form")).to_be_visible()
        expect(page.locator("#scan-url")).to_be_visible()
        expect(page.locator("#scan-btn")).to_be_visible()
        expect(page.locator("#scan-btn")).to_have_text("Analyseer")

    def test_homepage_has_dutch_description(self, page: Page):
        page.goto(BASE_URL)

        # Description is in Dutch (first p inside scan-form, not the status text)
        expect(page.locator(".scan-form > p").first).to_contain_text("SaaS-dienst")

    def test_homepage_has_eupl_footer(self, page: Page):
        page.goto(BASE_URL)

        expect(page.locator("footer")).to_contain_text("EUPL-1.2")

    def test_url_input_has_placeholder(self, page: Page):
        page.goto(BASE_URL)

        url_input = page.locator("#scan-url")
        expect(url_input).to_have_attribute("placeholder", "https://app.leverancier.nl")
        expect(url_input).to_have_attribute("type", "url")
        expect(url_input).to_have_attribute("required", "")


class TestHealthEndpoints:
    """Health endpoints respond correctly."""

    def test_healthz_returns_ok(self, page: Page):
        response = page.request.get(f"{BASE_URL}/healthz")
        assert response.ok
        assert response.json()["status"] == "ok"

    def test_readyz_returns_ok(self, page: Page):
        response = page.request.get(f"{BASE_URL}/readyz")
        assert response.ok
        assert response.json()["status"] == "ok"


class TestScanSubmission:
    """User submits a URL for scanning."""

    def test_submit_valid_url_redirects_to_results(self, page: Page):
        page.goto(BASE_URL)

        # Fill in URL and submit
        page.fill("#scan-url", "https://www.example.com")
        page.click("#scan-btn")

        # Should redirect to results page with UUID in URL
        page.wait_for_url(re.compile(r"/results/[0-9a-f-]+"), timeout=10000)

        # Results page should show loading state
        expect(page.locator("#loading")).to_be_visible()

    def test_scan_api_returns_201_with_uuid(self, page: Page):
        response = page.request.post(
            f"{BASE_URL}/api/scan",
            data={"url": "https://www.example.com"},
        )
        assert response.status == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"
        assert data["url"] == "https://www.example.com/"

    def test_scan_result_retrievable_by_id(self, page: Page):
        # Create a scan
        create_response = page.request.post(
            f"{BASE_URL}/api/scan",
            data={"url": "https://www.example.com"},
        )
        scan_id = create_response.json()["id"]

        # Retrieve it
        get_response = page.request.get(f"{BASE_URL}/api/scan/{scan_id}")
        assert get_response.ok
        data = get_response.json()
        assert data["id"] == scan_id
        assert data["url"] == "https://www.example.com/"


class TestResultsPage:
    """User views the results page."""

    def test_results_page_shows_loading_or_error(self, page: Page):
        """Results page shows either loading spinner or error message.
        Without Lookyloo running, scan quickly moves to error status."""
        response = page.request.post(
            f"{BASE_URL}/api/scan",
            data={"url": "https://www.example.com"},
        )
        scan_id = response.json()["id"]

        page.goto(f"{BASE_URL}/results/{scan_id}")

        # Should show loading container (spinner or error text)
        expect(page.locator("#loading")).to_be_visible()
        # Page should have the results container structure
        expect(page.locator("#results-container")).to_be_visible()

    def test_results_page_has_correct_structure(self, page: Page):
        response = page.request.post(
            f"{BASE_URL}/api/scan",
            data={"url": "https://www.example.com"},
        )
        scan_id = response.json()["id"]

        page.goto(f"{BASE_URL}/results/{scan_id}")

        # Results container exists (hidden until data loads)
        expect(page.locator("#results-container")).to_be_visible()

        # The hidden results section has the right cards
        assert page.locator("#card-us").count() == 1
        assert page.locator("#card-eu").count() == 1
        assert page.locator("#card-unknown").count() == 1
        assert page.locator("#ip-table").count() == 1


# ===================== UNHAPPY FLOWS =====================


class TestInvalidInput:
    """User provides invalid input."""

    def test_empty_url_prevented_by_browser(self, page: Page):
        page.goto(BASE_URL)

        # Click without entering URL — browser validation should prevent submit
        page.click("#scan-btn")

        # Should still be on homepage (no redirect)
        expect(page).to_have_url(BASE_URL + "/")

    def test_invalid_url_format_rejected(self, page: Page):
        response = page.request.post(
            f"{BASE_URL}/api/scan",
            data={"url": "not-a-valid-url"},
        )
        # FastAPI/Pydantic validation error
        assert response.status == 422

    def test_ssrf_internal_ip_blocked(self, page: Page):
        """SSRF protection: internal IPs should be rejected."""
        response = page.request.post(
            f"{BASE_URL}/api/scan",
            data={"url": "http://127.0.0.1/admin"},
        )
        assert response.status == 422

    def test_ssrf_private_network_blocked(self, page: Page):
        """SSRF protection: RFC-1918 addresses should be rejected."""
        response = page.request.post(
            f"{BASE_URL}/api/scan",
            data={"url": "http://192.168.1.1/"},
        )
        assert response.status == 422


class TestNotFound:
    """User tries to access non-existent resources."""

    def test_nonexistent_scan_returns_404(self, page: Page):
        response = page.request.get(
            f"{BASE_URL}/api/scan/00000000-0000-0000-0000-000000000000"
        )
        assert response.status == 404
        assert "niet gevonden" in response.json()["detail"].lower()

    def test_invalid_scan_id_format_returns_422(self, page: Page):
        response = page.request.get(f"{BASE_URL}/api/scan/not-a-uuid")
        assert response.status == 422


class TestStaticAssets:
    """CSS and JS files load correctly."""

    def test_css_loads(self, page: Page):
        response = page.request.get(f"{BASE_URL}/static/style.css")
        assert response.ok
        assert "font-family" in response.text()

    def test_js_loads(self, page: Page):
        response = page.request.get(f"{BASE_URL}/static/app.js")
        assert response.ok
        assert "scan-form" in response.text()

    def test_no_console_errors_on_homepage(self, page: Page):
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        assert len(errors) == 0, f"Console errors: {errors}"
