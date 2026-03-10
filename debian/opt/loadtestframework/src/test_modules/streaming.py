import json
import time
import urllib.request
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright
from src.utils.error_logger import log_error


@dataclass
class StreamingResult:
    url: str
    # Metrics dataclass
    initial_buffer_time: float      # ms - time until video starts playing
    test_wall_seconds: float        # seconds - total wall clock time of the test
    startup_latency_sec: float      # seconds - time until video starts playing
    playback_seconds: float         # seconds - total seconds of video played
    active_playback_seconds: float  # seconds - actual playback time excluding buffering
    rebuffer_events: int            # number of rebuffering events after initial play
    rebuffer_ratio: float           # ratio of rebuffer time to total playback time
    min_buffer: float               # seconds - minimum buffer level observed
    max_buffer: float               # seconds - maximum buffer level observed
    avg_buffer: float               # seconds - average buffer level
    resolution_switches: int        # number of resolution/quality changes
    segments_fetched: int           # number of video segments fetched
    non_200_segments: int           # segments that got non-200 responses
    avg_segment_latency_sec: float  # seconds - average latency for segment fetches
    max_segment_latency_sec: float  # seconds - max latency for segment fetches
    est_bitrate_bps: float          # estimated bitrate in bits per second
    error_count: int                # number of errors encountered
    # Network metrics (averaged across entire test)
    download_speed: float           # Mbps - average download speed during test
    upload_speed: float             # Mbps - average upload speed during test
    latency: float                  # ms - average request-response RTT
    jitter: float                   # ms - standard deviation of latency


def run_streaming_test(parameters: dict) -> list[StreamingResult]:
    """
    Run Jellyfin streaming tests using Playwright.
    Videos play from start to end without duration limit.

    Args:
        parameters: dict with:
            - 'server_url' (str, Jellyfin server base URL)
            - 'api_key' (str, Jellyfin API key)
            - 'item_ids' (list of Jellyfin item IDs)
            - 'headless' (bool, default True)
            - 'disable_cache' (bool, default False)
            - 'parallel_browsing' (bool, default False) - run videos in parallel
            - 'aggregate' (bool, default False) - aggregate results into single result

    Returns:
        List of StreamingResult for each item (or single aggregated result if aggregate=True)
    """
    server_url = parameters.get("server_url", "")
    api_key = parameters.get("api_key", "")
    item_ids = parameters.get("item_ids", [])
    headless = parameters.get("headless", True)
    disable_cache = parameters.get("disable_cache", False)
    parallel_browsing = parameters.get("parallel_browsing", False)
    aggregate = parameters.get("aggregate", False)

    # Fetch server info needed for browser authentication
    server_id, user_id = _get_jellyfin_server_info(server_url, api_key)

    # Construct playback URLs for each item
    base = server_url.rstrip("/")
    playback_urls = [f"{base}/web/index.html#!/details?id={item_id}" for item_id in item_ids]

    if parallel_browsing and len(playback_urls) > 1:
        results = _run_parallel_streaming(playback_urls, headless, disable_cache, server_url, api_key, server_id, user_id)
    else:
        results = _run_sequential_streaming(playback_urls, headless, disable_cache, server_url, api_key, server_id, user_id)

    if aggregate and len(results) > 1:
        return [_aggregate_results(results)]

    return results


def _aggregate_results(results: list[StreamingResult]) -> StreamingResult:
    """Aggregate multiple StreamingResult objects into a single result."""
    n = len(results)
    if n == 0:
        raise ValueError("Cannot aggregate empty results list")

    if n == 1:
        return results[0]

    # Combine URLs
    aggregated_url = ", ".join(r.url for r in results)

    # Calculate aggregated metrics
    return StreamingResult(
        url=aggregated_url,
        # Averages for time-based metrics
        initial_buffer_time=sum(r.initial_buffer_time for r in results) / n,
        test_wall_seconds=sum(r.test_wall_seconds for r in results) / n,
        startup_latency_sec=sum(r.startup_latency_sec for r in results) / n,
        playback_seconds=sum(r.playback_seconds for r in results) / n,
        active_playback_seconds=sum(r.active_playback_seconds for r in results) / n,
        # Sums for count-based metrics
        rebuffer_events=sum(r.rebuffer_events for r in results),
        # Average for ratio
        rebuffer_ratio=sum(r.rebuffer_ratio for r in results) / n,
        # Min/max/avg for buffer metrics
        min_buffer=min(r.min_buffer for r in results),
        max_buffer=max(r.max_buffer for r in results),
        avg_buffer=sum(r.avg_buffer for r in results) / n,
        # Sums for count-based metrics
        resolution_switches=sum(r.resolution_switches for r in results),
        segments_fetched=sum(r.segments_fetched for r in results),
        non_200_segments=sum(r.non_200_segments for r in results),
        # Averages and max for latency metrics
        avg_segment_latency_sec=sum(r.avg_segment_latency_sec for r in results) / n,
        max_segment_latency_sec=max(r.max_segment_latency_sec for r in results),
        # Average for bitrate
        est_bitrate_bps=sum(r.est_bitrate_bps for r in results) / n,
        # Sum for error count
        error_count=sum(r.error_count for r in results),
        # Averages for network metrics
        download_speed=sum(r.download_speed for r in results) / n,
        upload_speed=sum(r.upload_speed for r in results) / n,
        latency=sum(r.latency for r in results) / n,
        jitter=sum(r.jitter for r in results) / n,
    )


def _run_sequential_streaming(playback_urls: list, headless: bool, disable_cache: bool,
                               server_url: str, api_key: str,
                               server_id: str, user_id: str) -> list[StreamingResult]:
    """Run streaming tests sequentially (one video at a time)."""
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--disable-blink-features=AutomationControlled",
                # Linux/Debian compatibility flags
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        if disable_cache:
            _disable_cache_for_context(context)

        _setup_jellyfin_auth(context, server_url, api_key, server_id, user_id)

        for url in playback_urls:
            result = _stream_video(context, url)
            results.append(result)

        browser.close()

    return results


def _stream_single_video(url: str, headless: bool, disable_cache: bool,
                          server_url: str, api_key: str,
                          server_id: str, user_id: str) -> StreamingResult:
    """Stream a single video in its own browser instance (for parallel execution)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        if disable_cache:
            _disable_cache_for_context(context)

        _setup_jellyfin_auth(context, server_url, api_key, server_id, user_id)

        result = _stream_video(context, url)
        browser.close()

    return result


def _run_parallel_streaming(playback_urls: list, headless: bool, disable_cache: bool,
                             server_url: str, api_key: str,
                             server_id: str, user_id: str) -> list[StreamingResult]:
    """Run streaming tests in parallel (each video in its own browser instance)."""
    results = []
    with ThreadPoolExecutor(max_workers=len(playback_urls)) as executor:
        future_to_url = {
            executor.submit(_stream_single_video, url, headless, disable_cache, server_url, api_key, server_id, user_id): url
            for url in playback_urls
        }
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                log_error("streaming", "_run_parallel_streaming", e, context=f"url={url}")
                # Create error result for failed video
                results.append(StreamingResult(
                    url=url,
                    initial_buffer_time=-1,
                    test_wall_seconds=-1,
                    startup_latency_sec=-1,
                    playback_seconds=-1,
                    active_playback_seconds=-1,
                    rebuffer_events=0,
                    rebuffer_ratio=-1,
                    min_buffer=-1,
                    max_buffer=-1,
                    avg_buffer=-1,
                    resolution_switches=0,
                    segments_fetched=0,
                    non_200_segments=0,
                    avg_segment_latency_sec=-1,
                    max_segment_latency_sec=-1,
                    est_bitrate_bps=-1,
                    error_count=1,
                    download_speed=-1,
                    upload_speed=-1,
                    latency=-1,
                    jitter=-1,
                ))
    return results


def _get_jellyfin_server_info(server_url: str, api_key: str) -> tuple[str, str]:
    """Fetch ServerId and UserId from Jellyfin API.

    Returns:
        Tuple of (server_id, user_id)
    """
    base = server_url.rstrip("/")
    headers = {"X-Emby-Token": api_key}

    # Get server ID
    server_id = ""
    try:
        req = urllib.request.Request(f"{base}/System/Info", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            server_id = data.get("Id", "")
    except Exception as e:
        log_error("streaming", "_get_jellyfin_server_info", e, context=f"Failed to fetch server ID from {base}")

    # Get user ID (first user returned by API)
    user_id = ""
    try:
        req = urllib.request.Request(f"{base}/Users", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            users = json.loads(resp.read().decode())
            if users:
                user_id = users[0].get("Id", "")
    except Exception as e:
        log_error("streaming", "_get_jellyfin_server_info", e, context=f"Failed to fetch user ID from {base}")

    return server_id, user_id


def _setup_jellyfin_auth(context, server_url: str, api_key: str,
                          server_id: str, user_id: str) -> None:
    """Authenticate the browser session with Jellyfin via localStorage credentials."""
    base = server_url.rstrip("/")

    # Navigate to Jellyfin web root to establish the origin for localStorage
    page = context.new_page()
    page.goto(f"{base}/web/index.html", wait_until="domcontentloaded")

    # Set jellyfin_credentials in localStorage (the format the web client expects)
    credentials = json.dumps({
        "Servers": [{
            "ManualAddress": base,
            "Id": server_id,
            "AccessToken": api_key,
            "UserId": user_id,
            "DateLastAccessed": int(time.time() * 1000),
        }]
    })
    page.evaluate(f"() => localStorage.setItem('jellyfin_credentials', {json.dumps(credentials)})")
    page.close()

    # Also inject auth header on all requests to the server for media streams
    def inject_auth(route):
        headers = {**route.request.headers, "X-Emby-Token": api_key}
        route.continue_(headers=headers)

    context.route(f"{base}/**", inject_auth)


def _disable_cache_for_context(context) -> None:
    """Disable browser caching for a context using CDP."""
    page = context.new_page()
    cdp = page.context.new_cdp_session(page)
    cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
    page.close()


def _stream_video(context, url: str) -> StreamingResult:
    """Stream a Jellyfin video end-to-end and collect metrics."""
    page = context.new_page()

    # Initialize metrics tracking
    metrics = {
        "initial_buffer_time": 0.0,
        "test_wall_seconds": 0.0,
        "startup_latency_sec": 0.0,
        "playback_seconds": 0.0,
        "active_playback_seconds": 0.0,
        "rebuffer_events": 0,
        "rebuffer_ratio": 0.0,
        "min_buffer": float('inf'),
        "max_buffer": 0.0,
        "buffer_samples": [],
        "resolution_switches": 0,
        "segments_fetched": 0,
        "non_200_segments": 0,
        "segment_latencies": [],
        "est_bitrate_bps": 0.0,
        "error_count": 0,
        "total_rebuffer_time": 0.0,
        # Network metrics tracking
        "bytes_received": 0,
        "bytes_sent": 0,
        "all_latencies": [],  # RTT for all requests (ms)
    }

    # Track requests via network interception
    request_tracking = {"pending": {}}

    def handle_request(request):
        req_url = request.url
        request_tracking["pending"][req_url] = time.time()
        # Track upload bytes from request body
        try:
            post_data = request.post_data
            if post_data:
                metrics["bytes_sent"] += len(post_data.encode('utf-8') if isinstance(post_data, str) else post_data)
        except Exception:
            pass

    def handle_response(response):
        req_url = response.url
        rtt_ms = 0.0
        # Track latency for all requests
        if req_url in request_tracking["pending"]:
            start_time = request_tracking["pending"].pop(req_url)
            rtt_ms = (time.time() - start_time) * 1000
            metrics["all_latencies"].append(rtt_ms)

        # Track download bytes from content-length header
        try:
            content_length = response.headers.get("content-length", "0")
            metrics["bytes_received"] += int(content_length)
        except (ValueError, TypeError):
            pass

        # Track video segment specific metrics (Jellyfin URL patterns)
        if any(pattern in req_url for pattern in ["/Videos/", "/hls/", ".ts", ".m3u8", "/stream", "/Audio/"]):
            if rtt_ms > 0:
                metrics["segment_latencies"].append(rtt_ms / 1000)  # Convert to seconds
            metrics["segments_fetched"] += 1
            if response.status != 200:
                metrics["non_200_segments"] += 1

    def handle_request_failed(request):
        req_url = request.url
        if req_url in request_tracking["pending"]:
            request_tracking["pending"].pop(req_url)
            metrics["error_count"] += 1

    page.on("request", handle_request)
    page.on("response", handle_response)
    page.on("requestfailed", handle_request_failed)

    test_start_time = time.time()

    try:
        page.goto(url, wait_until="domcontentloaded")

        # Click the Play button on the Jellyfin details page to start playback
        _click_jellyfin_play(page)

        # Wait for video player to load
        page.wait_for_selector("video", timeout=15000)

        # Click to play if video is paused
        _ensure_video_playing(page)

        # Measure initial buffer time (time until video starts playing)
        initial_buffer_time_ms = _measure_initial_buffer_time(page)
        metrics["initial_buffer_time"] = initial_buffer_time_ms
        metrics["startup_latency_sec"] = initial_buffer_time_ms / 1000.0

        # Monitor playback until video ends
        _monitor_full_playback(page, metrics)

    except Exception as e:
        log_error("streaming", "_stream_video", e, context=f"url={url}")
        metrics["error_count"] += 1
    finally:
        page.close()

    test_end_time = time.time()
    metrics["test_wall_seconds"] = test_end_time - test_start_time

    # Calculate derived metrics
    if metrics["buffer_samples"]:
        metrics["avg_buffer"] = sum(metrics["buffer_samples"]) / len(metrics["buffer_samples"])
        if metrics["min_buffer"] == float('inf'):
            metrics["min_buffer"] = 0.0
    else:
        metrics["min_buffer"] = 0.0
        metrics["avg_buffer"] = 0.0

    # Calculate rebuffer ratio
    total_time = metrics["playback_seconds"] + metrics["total_rebuffer_time"]
    if total_time > 0:
        metrics["rebuffer_ratio"] = metrics["total_rebuffer_time"] / total_time

    # Active playback = total playback - rebuffer time
    metrics["active_playback_seconds"] = max(0, metrics["playback_seconds"] - metrics["total_rebuffer_time"])

    # Calculate segment latency stats
    if metrics["segment_latencies"]:
        metrics["avg_segment_latency_sec"] = sum(metrics["segment_latencies"]) / len(metrics["segment_latencies"])
        metrics["max_segment_latency_sec"] = max(metrics["segment_latencies"])
    else:
        metrics["avg_segment_latency_sec"] = 0.0
        metrics["max_segment_latency_sec"] = 0.0

    # Estimate bitrate from network bytes and playback duration
    if metrics["playback_seconds"] > 0:
        metrics["est_bitrate_bps"] = (metrics["bytes_received"] * 8) / metrics["playback_seconds"]

    # Calculate network metrics (download_speed, upload_speed, latency, jitter)
    duration_seconds = metrics["test_wall_seconds"]
    if duration_seconds > 0:
        # Convert bytes to Mbps: (bytes * 8) / (seconds * 1,000,000)
        metrics["download_speed"] = (metrics["bytes_received"] * 8) / (duration_seconds * 1_000_000)
        metrics["upload_speed"] = (metrics["bytes_sent"] * 8) / (duration_seconds * 1_000_000)
    else:
        metrics["download_speed"] = 0.0
        metrics["upload_speed"] = 0.0

    # Calculate average latency and jitter from all request RTTs
    all_latencies = metrics["all_latencies"]
    if all_latencies:
        metrics["latency"] = sum(all_latencies) / len(all_latencies)
        # Jitter = standard deviation of latencies
        if len(all_latencies) > 1:
            mean = metrics["latency"]
            variance = sum((x - mean) ** 2 for x in all_latencies) / len(all_latencies)
            metrics["jitter"] = variance ** 0.5
        else:
            metrics["jitter"] = 0.0
    else:
        metrics["latency"] = 0.0
        metrics["jitter"] = 0.0

    return StreamingResult(
        url=url,
        initial_buffer_time=metrics["initial_buffer_time"],
        test_wall_seconds=metrics["test_wall_seconds"],
        startup_latency_sec=metrics["startup_latency_sec"],
        playback_seconds=metrics["playback_seconds"],
        active_playback_seconds=metrics["active_playback_seconds"],
        rebuffer_events=metrics["rebuffer_events"],
        rebuffer_ratio=metrics["rebuffer_ratio"],
        min_buffer=metrics["min_buffer"],
        max_buffer=metrics["max_buffer"],
        avg_buffer=metrics["avg_buffer"],
        resolution_switches=metrics["resolution_switches"],
        segments_fetched=metrics["segments_fetched"],
        non_200_segments=metrics["non_200_segments"],
        avg_segment_latency_sec=metrics["avg_segment_latency_sec"],
        max_segment_latency_sec=metrics["max_segment_latency_sec"],
        est_bitrate_bps=metrics["est_bitrate_bps"],
        error_count=metrics["error_count"],
        download_speed=metrics["download_speed"],
        upload_speed=metrics["upload_speed"],
        latency=metrics["latency"],
        jitter=metrics["jitter"],
    )


def _click_jellyfin_play(page) -> None:
    """Click the Play button on the Jellyfin item details page to start video playback."""
    try:
        play_btn = page.locator(
            'button[data-action="play"], '
            'button.btnPlay, '
            'button:has-text("Play")'
        )
        play_btn.first.click(timeout=10000)
        page.wait_for_timeout(1000)
    except Exception as e:
        log_error("streaming", "_click_jellyfin_play", e)


def _ensure_video_playing(page) -> None:
    """Ensure the video is playing, clicking play if needed."""
    try:
        is_paused = page.evaluate("""() => {
            const video = document.querySelector('video');
            return video ? video.paused : true;
        }""")

        if is_paused:
            # Try clicking the video element directly
            video = page.locator('video')
            if video.is_visible(timeout=2000):
                video.click()
            else:
                # Fallback to Jellyfin play button selectors
                play_button = page.locator(
                    'button[data-action="play"], '
                    'button.btnPlay, '
                    'button:has-text("Play")'
                )
                if play_button.first.is_visible(timeout=2000):
                    play_button.first.click()

            page.wait_for_timeout(500)
    except Exception as e:
        log_error("streaming", "_ensure_video_playing", e)


def _measure_initial_buffer_time(page) -> float:
    """Measure time until video starts playing."""
    start_time = time.time()
    max_wait = 30  # seconds

    while (time.time() - start_time) < max_wait:
        try:
            state = page.evaluate("""() => {
                const video = document.querySelector('video');
                if (!video) return { playing: false, time: 0 };
                return {
                    playing: !video.paused && video.currentTime > 0,
                    time: video.currentTime
                };
            }""")

            if state.get("playing") and state.get("time", 0) > 0:
                return (time.time() - start_time) * 1000
        except Exception as e:
            log_error("streaming", "_measure_initial_buffer_time", e)

        time.sleep(0.1)

    return (time.time() - start_time) * 1000


def _monitor_full_playback(page, metrics: dict) -> None:
    """Monitor video playback until it ends and collect metrics."""
    last_resolution = None
    was_buffering = False
    buffer_start_time = None
    last_current_time = 0
    stall_count = 0
    max_stall_checks = 10  # Max consecutive stalls before considering video ended
    no_video_count = 0     # Consecutive checks with no <video> element
    player_url = page.url  # Capture URL while in the video player

    while True:
        # Detect if Jellyfin navigated away from the video player
        # (e.g., back to home/details page after playback ended)
        try:
            current_url = page.url
            if current_url != player_url:
                break
        except Exception:
            break

        try:
            state = page.evaluate("""() => {
                const video = document.querySelector('video');
                if (!video) return null;

                const quality = video.getVideoPlaybackQuality ?
                    video.getVideoPlaybackQuality() : {};

                // Resolution from actual video dimensions (standard HTML5)
                let resolution = 'unknown';
                if (video.videoWidth > 0 && video.videoHeight > 0) {
                    resolution = video.videoHeight + 'p';
                }

                // Calculate buffer ahead (standard HTML5 buffered ranges)
                let bufferAhead = 0;
                if (video.buffered.length > 0) {
                    for (let i = 0; i < video.buffered.length; i++) {
                        if (video.buffered.start(i) <= video.currentTime &&
                            video.buffered.end(i) >= video.currentTime) {
                            bufferAhead = video.buffered.end(i) - video.currentTime;
                            break;
                        }
                    }
                }

                return {
                    currentTime: video.currentTime,
                    duration: video.duration,
                    paused: video.paused,
                    ended: video.ended,
                    readyState: video.readyState,
                    bufferAhead: bufferAhead,
                    droppedFrames: quality.droppedVideoFrames || 0,
                    totalFrames: quality.totalVideoFrames || 0,
                    resolution: resolution,
                    waiting: video.seeking || video.readyState < 3,
                    networkState: video.networkState
                };
            }""")

            if not state:
                no_video_count += 1
                if no_video_count >= 3:
                    # Video element gone (Jellyfin navigated away after playback ended)
                    break
                time.sleep(0.5)
                continue
            no_video_count = 0

            # Check if video ended
            if state.get("ended", False):
                metrics["playback_seconds"] = state.get("currentTime", 0)
                break

            # Check for stall (video not progressing)
            current_time = state.get("currentTime", 0)
            if current_time <= last_current_time and not state.get("paused", False):
                stall_count += 1
                if stall_count >= max_stall_checks:
                    # Video seems stuck or ended
                    metrics["playback_seconds"] = current_time
                    break
            else:
                stall_count = 0
            last_current_time = current_time

            # Track buffering (rebuffering events after initial play)
            is_buffering = state.get("waiting", False) or state.get("readyState", 4) < 3

            if is_buffering and not was_buffering:
                buffer_start_time = time.time()
                metrics["rebuffer_events"] += 1
            elif not is_buffering and was_buffering and buffer_start_time:
                rebuffer_duration = time.time() - buffer_start_time
                metrics["total_rebuffer_time"] += rebuffer_duration

            was_buffering = is_buffering

            # Track buffer levels
            buffer_ahead = state.get("bufferAhead", 0)
            if buffer_ahead > 0:
                metrics["buffer_samples"].append(buffer_ahead)
                if buffer_ahead < metrics["min_buffer"]:
                    metrics["min_buffer"] = buffer_ahead
                if buffer_ahead > metrics["max_buffer"]:
                    metrics["max_buffer"] = buffer_ahead

            # Track resolution changes
            current_resolution = state.get("resolution", "unknown")
            if last_resolution and current_resolution != last_resolution and current_resolution != "unknown":
                metrics["resolution_switches"] += 1
            if current_resolution != "unknown":
                last_resolution = current_resolution

            # Update playback duration
            metrics["playback_seconds"] = current_time

        except Exception as e:
            log_error("streaming", "_monitor_full_playback", e)
            metrics["error_count"] += 1

        time.sleep(0.5)


if __name__ == "__main__":
    params = {
        "server_url": "http://20.219.59.36:8096",
        "api_key": "c68f4199610848f0bb1e59505e556f7e",
        "item_ids": ["1ec6084ffc9e4dd3454696bfe04ff4dd","b6c911fdf779cacbb9bbad3c9f0c5f8c"], # Samsung, 8K i guess
        "headless": False,
        "parallel_browsing": True,
        "aggregate": False
    }
    results = run_streaming_test(parameters=params)
    for r in results:
        print(f"URL: {r.url}")
        print(f"  Test Wall Seconds: {r.test_wall_seconds:.2f}s")
        print(f"  Startup Latency: {r.startup_latency_sec:.2f}s")
        print(f"  Initial Buffer Time: {r.initial_buffer_time:.2f}ms")
        print(f"  Active Playback: {r.active_playback_seconds:.2f}s")
        print(f"  Rebuffer Events: {r.rebuffer_events}")
        print(f"  Rebuffer Ratio: {r.rebuffer_ratio:.4f}")
        print(f"  Buffer (min/avg/max): {r.min_buffer:.2f}/{r.avg_buffer:.2f}/{r.max_buffer:.2f}s")
        print(f"  Resolution Switches: {r.resolution_switches}")
        print(f"  Segments Fetched: {r.segments_fetched}")
        print(f"  Non-200 Segments: {r.non_200_segments}")
        print(f"  Segment Latency (avg/max): {r.avg_segment_latency_sec:.3f}/{r.max_segment_latency_sec:.3f}s")
        print(f"  Est Bitrate: {r.est_bitrate_bps:.0f} bps")
        print(f"  Errors: {r.error_count}")
        print(f"  --- Network Metrics (Averaged) ---")
        print(f"  Download Speed: {r.download_speed:.2f} Mbps")
        print(f"  Upload Speed: {r.upload_speed:.2f} Mbps")
        print(f"  Latency: {r.latency:.2f} ms")
        print(f"  Jitter: {r.jitter:.2f} ms")
