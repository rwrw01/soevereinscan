import asyncio
import json
import logging
import socket
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class CaptureResult:
    """Result of a website capture with all extracted data."""
    hostname_ips: dict[str, list[str]] = field(default_factory=dict)
    all_ips: set[str] = field(default_factory=set)
    cookies: list[dict] = field(default_factory=list)
    third_party_domains: set[str] = field(default_factory=set)
    redirects: list[str] = field(default_factory=list)
    screenshot: bytes | None = None
    resource_tree: dict | None = None
    error: str | None = None


class CaptureService:
    """Captures web pages using playwrightcapture and analyzes with har2tree.

    Uses the same anti-detection and cookie consent logic as Lookyloo,
    but without the Lookyloo server, Redis, or any extra containers.
    """

    async def capture(self, url: str, timeout: int = 90) -> CaptureResult:
        """Capture a URL and extract all contacted hosts, IPs, and cookies."""
        result = CaptureResult()

        try:
            from playwrightcapture import Capture

            cap = Capture(browser="chromium")
            cap.locale = "nl-NL"
            cap.timezone_id = "Europe/Amsterdam"
            cap.color_scheme = "light"

            # Start Playwright manually so we can add --no-sandbox for containers
            # This replicates __aenter__ but with custom browser args
            import os
            from tempfile import NamedTemporaryFile
            from playwright.async_api import async_playwright

            os.environ["PW_TEST_SCREENSHOT_NO_FONTS_READY"] = "1"
            cap.playwright = await async_playwright().start()
            cap.browser = await cap.playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--unsafely-treat-insecure-origin-as-secure",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            cap._already_captured = set()
            cap._temp_harfile = NamedTemporaryFile(
                delete=False, prefix="playwright_capture_har", suffix=".json"
            )
            try:
                await cap.initialize_context()
                entries = await cap.capture_page(
                    url,
                    max_depth_capture_time=timeout,
                    allow_tracking=True,
                )
            finally:
                await cap.browser.close()
                await cap.playwright.stop()

            if not entries or not entries.get("har"):
                result.error = "Capture returned no HAR data"
                return result

            # Extract data from HAR
            har_data = entries["har"]
            result.screenshot = entries.get("png")
            result.redirects = [entries.get("last_redirected_url", url)]

            # Parse cookies from capture
            if entries.get("cookies"):
                result.cookies = entries["cookies"]

            # Extract hostnames and resolve IPs from HAR entries
            scan_domain = urlparse(url).netloc
            seen_hosts: set[str] = set()

            if isinstance(har_data, dict):
                log = har_data.get("log", {})
                har_entries = log.get("entries", [])
            else:
                har_entries = []

            for entry in har_entries:
                req_url = entry.get("request", {}).get("url", "")
                if not req_url:
                    continue

                hostname = urlparse(req_url).hostname
                if not hostname:
                    continue

                seen_hosts.add(hostname)

                if hostname != scan_domain and not hostname.endswith(f".{scan_domain}"):
                    result.third_party_domains.add(hostname)

                # Resolve hostname to IPs if not already done
                if hostname not in result.hostname_ips:
                    ips = await self._resolve_hostname(hostname)
                    if ips:
                        result.hostname_ips[hostname] = ips
                        result.all_ips.update(ips)

            # Try har2tree for richer cookie analysis
            try:
                result.cookies = self._analyze_cookies_from_har(har_data, url)
            except Exception:
                logger.debug("har2tree cookie analysis failed, using basic cookies", exc_info=True)

            # Build resource tree from HAR entries
            try:
                result.resource_tree = self._build_resource_tree(har_entries, url)
            except Exception:
                logger.debug("Resource tree building failed", exc_info=True)

        except ImportError:
            logger.error("playwrightcapture not installed")
            result.error = "playwrightcapture not installed"
        except Exception:
            logger.exception("Capture failed for %s", url)
            result.error = f"Capture failed for {url}"

        return result

    async def _resolve_hostname(self, hostname: str) -> list[str]:
        """Resolve hostname to IP addresses."""
        try:
            loop = asyncio.get_event_loop()
            infos = await loop.getaddrinfo(hostname, None, family=socket.AF_INET)
            return list({info[4][0] for info in infos})
        except (socket.gaierror, OSError):
            return []

    def _analyze_cookies_from_har(self, har_data: dict, url: str) -> list[dict]:
        """Use har2tree for deeper cookie analysis if available."""
        try:
            from har2tree import CrawledTree, Har2Tree

            # har2tree expects a HAR file path, write temp file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".har", delete=False) as f:
                json.dump(har_data, f)
                har_path = Path(f.name)

            try:
                tree = CrawledTree([har_path], str(uuid.uuid4()))
                tree.find_parents()
                tree.join_trees()

                cookies = []
                for urlnode in tree.root_hartree.url_tree.traverse():
                    # Received cookies (set by servers)
                    for cookie in getattr(urlnode, "cookies_received", []):
                        cookies.append({
                            "name": cookie.get("name", ""),
                            "domain": cookie.get("domain", ""),
                            "path": cookie.get("path", "/"),
                            "secure": cookie.get("secure", False),
                            "httpOnly": cookie.get("httpOnly", False),
                            "source_url": urlnode.name,
                            "third_party": urlnode.hostname != urlparse(url).netloc,
                            "type": "received",
                        })
                return cookies
            finally:
                har_path.unlink(missing_ok=True)
        except ImportError:
            logger.debug("har2tree not available, skipping deep cookie analysis")
            return []
        except Exception:
            logger.debug("har2tree analysis failed", exc_info=True)
            return []

    def _build_resource_tree(self, har_entries: list[dict], url: str) -> dict | None:
        """Build a domain dependency tree from HAR entries using the Referer header."""
        scan_domain = urlparse(url).netloc

        # Count requests per domain and track parent-child via Referer
        domain_counts: dict[str, int] = {}
        children_map: dict[str, set[str]] = {}

        for entry in har_entries:
            req = entry.get("request", {})
            req_url = req.get("url", "")
            if not req_url:
                continue

            hostname = urlparse(req_url).hostname
            if not hostname:
                continue

            domain_counts[hostname] = domain_counts.get(hostname, 0) + 1

            # Determine parent via Referer header
            headers = req.get("headers", [])
            referer = None
            for h in headers:
                if h.get("name", "").lower() == "referer":
                    referer = h.get("value", "")
                    break

            if referer:
                parent_host = urlparse(referer).hostname
                if parent_host and parent_host != hostname:
                    if parent_host not in children_map:
                        children_map[parent_host] = set()
                    children_map[parent_host].add(hostname)

        if not domain_counts:
            return None

        # Determine which domains are children of other domains
        all_children: set[str] = set()
        for kids in children_map.values():
            all_children.update(kids)

        def build_node(domain: str, visited: set[str]) -> dict:
            node: dict = {
                "domain": domain,
                "count": domain_counts.get(domain, 0),
                "children": [],
            }
            if domain in visited:
                return node
            visited = visited | {domain}
            for child in sorted(children_map.get(domain, [])):
                node["children"].append(build_node(child, visited))
            return node

        # Root is the scan domain; if absent, pick the domain with highest count
        root_domain = scan_domain if scan_domain in domain_counts else max(
            domain_counts, key=lambda d: domain_counts[d]
        )

        visited: set[str] = set()
        tree = build_node(root_domain, visited)

        # Add orphan domains (not root, not a child of anyone) as root children
        for domain in sorted(domain_counts):
            if domain != root_domain and domain not in all_children:
                tree["children"].append(build_node(domain, {root_domain, domain}))

        # Add all discovered hostnames that aren't already in the tree.
        # Many domains are loaded directly (no Referer) and would otherwise
        # be missed entirely.
        tree_domains = self._collect_tree_domains(tree)
        all_hostnames = set()
        for entry in har_entries:
            req_url = entry.get("request", {}).get("url", "")
            if req_url:
                hostname = urlparse(req_url).hostname
                if hostname:
                    all_hostnames.add(hostname)

        for hostname in sorted(all_hostnames):
            if hostname not in tree_domains:
                tree["children"].append({
                    "domain": hostname,
                    "count": domain_counts.get(hostname, 0),
                    "children": [],
                })

        return tree

    def _collect_tree_domains(self, node: dict) -> set[str]:
        """Recursively collect all domain names present in the tree."""
        domains = {node.get("domain", "")}
        for child in node.get("children", []):
            domains.update(self._collect_tree_domains(child))
        return domains

    @staticmethod
    def classify_third_party(scan_url: str, hostname: str) -> bool:
        """Check if hostname is third-party relative to scan URL."""
        scan_domain = urlparse(scan_url).netloc
        return hostname != scan_domain and not hostname.endswith(f".{scan_domain}")
