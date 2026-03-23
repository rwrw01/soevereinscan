import logging

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


async def generate_report_pdf(
    scan_id: str, base_url: str = "http://127.0.0.1:8000"
) -> bytes | None:
    """Generate PDF from the scan results page using Playwright."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = await browser.new_page(
                viewport={"width": 1280, "height": 900}
            )

            results_url = f"{base_url}/soeverein/results/{scan_id}"
            await page.goto(
                results_url, wait_until="networkidle", timeout=30000
            )

            # Wait for results to load (the JS polls the API)
            try:
                await page.wait_for_selector(
                    "#results:not(.hidden)", timeout=60000
                )
                # Give JS time to render all sections
                await page.wait_for_timeout(2000)
            except Exception:
                logger.warning(
                    "Results not loaded for PDF generation of %s", scan_id
                )
                await browser.close()
                return None

            # Open "Meer informatie" for the PDF
            meer_info = page.locator(
                "details summary:has-text('Meer informatie')"
            )
            if await meer_info.count() > 0:
                await meer_info.click()
                await page.wait_for_timeout(500)

            # Generate PDF with good pagination
            pdf_bytes = await page.pdf(
                format="A4",
                margin={
                    "top": "20mm",
                    "bottom": "20mm",
                    "left": "15mm",
                    "right": "15mm",
                },
                print_background=True,
                scale=0.85,
            )

            await browser.close()
            return pdf_bytes
    except Exception:
        logger.exception("PDF generation failed for scan %s", scan_id)
        return None
