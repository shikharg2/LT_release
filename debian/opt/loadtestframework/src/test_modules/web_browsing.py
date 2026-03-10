from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright
from src.utils.error_logger import log_error


@dataclass
class WebBrowsingResult:
    url: str
    page_load_time: float      # ms
    ttfb: float                # ms (time to first byte)
    dom_content_loaded: float  # ms
    http_response_code: int
    resource_count: int
    redirect_count: int
    error: str = ""


def run_web_browsing_test(parameters: dict) -> list[WebBrowsingResult]:
    """
    Run web browsing tests using Playwright.

    Args:
        parameters: dict with:
            - 'target_url' (list of URLs)
            - 'headless' (bool, default True)
            - 'disable_cache' (bool, default False) - disables browser caching
            - 'parallel_browsing' (bool, default False) - load all URLs in parallel

    Returns:
        List of WebBrowsingResult for each URL
    """
    target_urls = parameters.get("target_url", [])
    headless = parameters.get("headless", True)
    disable_cache = parameters.get("disable_cache", False)
    parallel_browsing = parameters.get("parallel_browsing", False)

    if parallel_browsing and len(target_urls) > 1:
        # Parallel execution: each thread gets its own browser instance
        return _run_parallel_browsing(target_urls, headless, disable_cache)

    # Sequential execution
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()

        if disable_cache:
            _disable_cache_for_context(context)

        for url in target_urls:
            result = _load_page(context, url)
            results.append(result)

        browser.close()

    return results


def _load_page_in_own_browser(url: str, headless: bool, disable_cache: bool) -> WebBrowsingResult:
    """Load a single page in its own browser instance (for parallel execution)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()

        if disable_cache:
            _disable_cache_for_context(context)

        result = _load_page(context, url)
        browser.close()

    return result


def _run_parallel_browsing(target_urls: list, headless: bool, disable_cache: bool) -> list[WebBrowsingResult]:
    """Run web browsing tests in parallel (each URL in its own browser instance)."""
    results = []
    with ThreadPoolExecutor(max_workers=len(target_urls)) as executor:
        future_to_url = {
            executor.submit(_load_page_in_own_browser, url, headless, disable_cache): url
            for url in target_urls
        }
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                log_error("web_browsing", "_run_parallel_browsing", e, context=f"url={url}")
                results.append(WebBrowsingResult(
                    url=url,
                    page_load_time=-1,
                    ttfb=-1,
                    dom_content_loaded=-1,
                    http_response_code=0,
                    resource_count=0,
                    redirect_count=0,
                    error=str(e)
                ))
    return results


def _disable_cache_for_context(context) -> None:
    """
    Disable browser caching for a context using CDP.
    Creates a temporary page to send the CDP command.
    """
    page = context.new_page()
    cdp = page.context.new_cdp_session(page)
    cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
    page.close()


def _load_page(context, url: str) -> WebBrowsingResult:
    """Load a single page and collect metrics."""
    page = context.new_page()

    resource_count = 0
    redirect_count = 0
    http_response_code = 0

    def on_response(response):
        nonlocal resource_count, redirect_count, http_response_code
        resource_count += 1
        if response.url == url or response.url == page.url:
            http_response_code = response.status
        if 300 <= response.status < 400:
            redirect_count += 1

    page.on("response", on_response)

    try:
        response = page.goto(url, wait_until="load")
        if response:
            http_response_code = response.status

        timing = page.evaluate("""() => {
            const perf = performance.getEntriesByType('navigation')[0];
            return {
                page_load_time: perf.loadEventEnd - perf.startTime,
                ttfb: perf.responseStart - perf.requestStart,
                dom_content_loaded: perf.domContentLoadedEventEnd - perf.startTime
            };
        }""")

        result = WebBrowsingResult(
            url=url,
            page_load_time=timing.get("page_load_time", 0),
            ttfb=timing.get("ttfb", 0),
            dom_content_loaded=timing.get("dom_content_loaded", 0),
            http_response_code=http_response_code,
            resource_count=resource_count,
            redirect_count=redirect_count
        )
    except Exception as e:
        log_error("web_browsing", "_load_page", e, context=f"url={url}")
        result = WebBrowsingResult(
            url=url,
            page_load_time=-1,
            ttfb=-1,
            dom_content_loaded=-1,
            http_response_code=0,
            resource_count=resource_count,
            redirect_count=redirect_count,
            error=str(e)
        )
    finally:
        page.close()

    return result

if __name__ == "__main__":
    params = {"target_url" : ["https://www.fasfasgoogle.com","https://www.youtugedtsfhesrwbe.com"], "headless": False, "parallel_browsing": False}
    results = run_web_browsing_test(parameters=params)
    print(results)
    