import subprocess
import json
import time
from dataclasses import dataclass
from src.utils.error_logger import log_error


@dataclass
class SpeedTestResult:
    download_speed: float  # Mbps
    upload_speed: float    # Mbps
    jitter: float          # ms
    latency: float         # ms


def run_speed_test(parameters: dict) -> list[SpeedTestResult]:
    """
    Run iperf3 speed tests based on parameters.

    Args:
        parameters: dict with 'target_url' (list of ip:port or domain:port)
                    and 'duration' (seconds)

    Returns:
        List of SpeedTestResult for each target URL
    """
    target_urls = parameters.get("target_url", [])
    duration = parameters.get("duration", 10)

    results = []
    for url in target_urls:
        host, port = _parse_url(url)
        result = _run_iperf3_test(host, port, duration)
        results.append(result)

    return results


def _parse_url(url: str) -> tuple[str, int]:
    """Parse ip:port or domain:port format."""
    parts = url.rsplit(":", 1)
    host = parts[0]
    port = int(parts[1]) if len(parts) > 1 else 5201
    return host, port


def _run_iperf3_test(host: str, port: int, duration: int) -> SpeedTestResult:
    """Run iperf3 test and collect metrics."""
    # TCP tests for accurate speed measurements
    # Download test (reverse mode - client receives from server)
    download_result = _execute_iperf3(host, port, duration, reverse=True, udp=False)
    download_speed = _extract_speed(download_result, reverse=True)

    # Measure latency via ping
    latency = _measure_latency_ping(host)

    # Small delay to avoid server rate limiting
    time.sleep(5)

    # Upload test (client sends to server)
    upload_result = _execute_iperf3(host, port, duration, reverse=False, udp=False)
    upload_speed = _extract_speed(upload_result, reverse=False)

    # Small delay before UDP test
    time.sleep(5)

    # UDP test for jitter measurement (may fail on some public servers)
    udp_result = _execute_iperf3(host, port, duration, reverse=False, udp=True)
    jitter = _extract_jitter(udp_result)

    return SpeedTestResult(
        download_speed=download_speed,
        upload_speed=upload_speed,
        jitter=jitter,
        latency=latency
    )


def _execute_iperf3(host: str, port: int, duration: int, reverse: bool, udp: bool = False) -> dict:
    """Execute iperf3 command and return JSON output."""
    cmd = [
        "iperf3",
        "-c", host,
        "-p", str(port),
        "-t", str(duration),
        "-J",  # JSON output,
        "-P", " 8",
        "-O", " 5",
        "-i", " 5"
        "--connect-timeout", "10000",
    ]
    if udp:
        cmd.append("-u")  # UDP mode for jitter measurement
    if reverse:
        cmd.append("-R")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 30)
        return json.loads(result.stdout) if result.stdout else {}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        log_error("speed_test", "_execute_iperf3", e, context=f"host={host}:{port}")
        return {}


def _extract_speed(data: dict, reverse: bool = False) -> float:
    """Extract speed in Mbps from iperf3 JSON output."""
    try:
        end = data.get("end", {})
        if reverse:
            # Download (reverse mode): client receives, use sum_received
            sum_data = end.get("sum_received", {}) or end.get("sum", {})
        else:
            # Upload (normal mode): client sends, use sum_sent
            sum_data = end.get("sum_sent", {}) or end.get("sum", {})
        bits_per_second = sum_data.get("bits_per_second", 0)
        return bits_per_second / 1_000_000
    except (KeyError, TypeError) as e:
        log_error("speed_test", "_extract_speed", e)
        return -1


def _extract_jitter(data: dict) -> float:
    """Extract jitter in ms from iperf3 JSON output."""
    try:
        end = data.get("end", {})
        sum_data = end.get("sum", {})
        return sum_data.get("jitter_ms", 0.0)
    except (KeyError, TypeError) as e:
        log_error("speed_test", "_extract_jitter", e)
        return -1


def _measure_latency_ping(host: str, count: int = 5) -> float:
    """Measure latency (avg RTT) in ms using ping."""
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", "5", host],
            capture_output=True, text=True, timeout=count * 6
        )
        if result.returncode != 0:
            log_error("speed_test", "_measure_latency_ping", Exception(f"ping returned non-zero exit code {result.returncode}"), context=f"host={host}")
            return -1
        # Parse "rtt min/avg/max/mdev = 1.234/5.678/9.012/1.234 ms"
        for line in result.stdout.splitlines():
            if "min/avg/max" in line:
                stats = line.split("=")[1].strip().split("/")
                return float(stats[1])  # avg value
        log_error("speed_test", "_measure_latency_ping", Exception("Could not parse ping output"), context=f"host={host}")
        return -1
    except (subprocess.TimeoutExpired, ValueError, IndexError, FileNotFoundError) as e:
        log_error("speed_test", "_measure_latency_ping", e, context=f"host={host}")
        return -1

if __name__ == "__main__":
    params = {
        "target_url":["20.219.59.36:5201"],
        "duration" : 30
    }
    results = run_speed_test(parameters=params)
    print(results)