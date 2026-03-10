import os
import shutil
import signal
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from src.utils.error_logger import log_error


@dataclass
class VoIPSIPpResult:
    # SIP signaling metrics
    call_success: float       # count
    call_setup_time: float    # ms (avg RTT)
    failed_calls: float       # count
    retransmissions: float    # count
    timeout_errors: float     # count
    avg_rtt: float            # ms
    min_rtt: float            # ms
    max_rtt: float            # ms
    sip_response_jitter: float  # ms - avg variation between consecutive SIP response times
    # Audio RTP metrics (from tshark capture)
    audio_rtp_packets: float = 0.0        # count - packets observed
    audio_rtp_packet_loss: float = 0.0    # count
    audio_rtp_packet_loss_rate: float = 0.0  # ratio 0-1
    audio_rtp_jitter: float = 0.0         # ms - RFC 3550 mean interarrival jitter
    audio_rtp_bitrate_kbps: float = 0.0   # kbps
    # Video RTP metrics (from tshark capture)
    video_rtp_packets: float = 0.0        # count
    video_rtp_packet_loss: float = 0.0    # count
    video_rtp_packet_loss_rate: float = 0.0  # ratio 0-1
    video_rtp_jitter: float = 0.0         # ms - RFC 3550 mean interarrival jitter
    video_rtp_bitrate_kbps: float = 0.0   # kbps
    # Aggregate media metrics
    jitter: float = 0.0                   # ms - real RTP interarrival jitter (avg across streams)
    media_capture_available: float = 0.0  # 1.0 if tshark was available, else 0.0
    media_streams_observed: float = 0.0   # count of RTP streams detected
    media_packets_sent: float = 0.0       # count
    media_packets_received: float = 0.0   # count
    media_bytes_sent: float = 0.0         # count
    media_bytes_received: float = 0.0     # count
    media_packet_loss: float = 0.0        # count
    media_packet_loss_rate: float = 0.0   # ratio 0-1
    media_tx_bitrate_kbps: float = 0.0    # kbps
    media_rx_bitrate_kbps: float = 0.0    # kbps


# Map user-facing transport names to SIPp -t flag values
_TRANSPORT_MAP = {
    "udp": "u1",
    "tcp": "t1",
}

# Map media type to scenario arguments
_SCENARIO_DIR = Path(__file__).resolve().parent.parent.parent / "sipp" / "sipp_scenarios"
_SCENARIO_MAP = {
    "none": None,  # uses built-in -sn uac
    "audio": _SCENARIO_DIR / "pfca_uac_apattern.xml",
    "video": _SCENARIO_DIR / "pfca_uac_vpattern.xml",
}

def run_voip_sipp_test(parameters: dict) -> list[VoIPSIPpResult]:
    """
    Run SIPp VoIP tests against remote UAS servers.

    Args:
        parameters: dict with 'target_url' (list of host or host:port),
                    and optional 'number_of_calls', 'call_duration',
                    'type', 'transport'. For UAS target endpoint:
                    none -> ip, audio -> ip:5061, video -> ip:5062.

    Returns:
        List of VoIPSIPpResult for each target URL
    """
    target_urls = parameters.get("target_url", [])
    number_of_calls = parameters.get("number_of_calls", 1)
    call_duration = parameters.get("call_duration", 5)
    media_type = parameters.get("type", "none")
    transport = parameters.get("transport", "udp")

    sipp_bin = _find_sipp_binary()
    results = []

    for url in target_urls:
        result = _run_single_test(
            sipp_bin, url, number_of_calls, call_duration, media_type, transport
        )
        results.append(result)

    return results


def _find_sipp_binary() -> str:
    """Find the SIPp binary on the system."""
    search_paths = [
        "/usr/bin/sipp",
        "/usr/local/bin/sipp",
        str(Path(__file__).resolve().parent.parent.parent / "sipp" / "sipp"),
    ]
    for path in search_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    which_result = shutil.which("sipp")
    if which_result:
        return which_result

    raise FileNotFoundError(
        "SIPp binary not found. Install it or place it in one of: "
        + ", ".join(search_paths)
    )


def _build_uas_target(target_url: str, media_type: str) -> str:
    """Build UAS target endpoint based on media type."""
    host = target_url.strip()

    if host.startswith("["):
        closing = host.find("]")
        host_only = host[:closing + 1] if closing != -1 else host
    elif host.count(":") == 1:
        host_only = host.rsplit(":", 1)[0]
    else:
        host_only = host

    if media_type == "audio":
        return f"{host_only}:5061"
    if media_type == "video":
        return f"{host_only}:5062"
    return host_only


def _run_single_test(
    sipp_bin: str,
    target_url: str,
    number_of_calls: int,
    call_duration: int,
    media_type: str,
    transport: str,
) -> VoIPSIPpResult:
    """Run a single SIPp test against one target and parse results."""
    uas_target = _build_uas_target(target_url, media_type)

    tmp_dir = tempfile.mkdtemp(prefix="sipp_trace_")
    stat_base = os.path.join(tmp_dir, "stat")

    try:
        cmd = _build_sipp_command(
            sipp_bin, uas_target, number_of_calls, call_duration,
            media_type, transport, stat_base,
        )
        timeout_sec = (call_duration * number_of_calls) + 60

        # Start tshark RTP capture (if available)
        pcap_file = os.path.join(tmp_dir, "rtp_capture.pcap")
        tshark_proc = _start_rtp_capture(pcap_file, timeout_sec)

        try:
            print(f"Running command: {cmd}")
            _run_sipp(cmd, timeout_sec, cwd=tmp_dir)
        finally:
            # Always stop tshark even if sipp fails
            _stop_rtp_capture(tshark_proc)

        # -stf controls stat file path; RTT file is auto-named <scenario>_<pid>_rtt.csv
        stat_file = _find_trace_file(tmp_dir, "stat")
        rtt_file = _find_trace_file(tmp_dir, "*_rtt*")

        stat_data = _parse_trace_stat(stat_file)
        rtt_data = _parse_trace_rtt(rtt_file)

        # Parse RTP media metrics from tshark capture
        rtp_data = _parse_rtp_streams(pcap_file, media_type)

        return VoIPSIPpResult(
            call_success=stat_data.get("successful_calls", 0.0),
            call_setup_time=rtt_data.get("avg", 0.0),
            failed_calls=stat_data.get("failed_calls", 0.0),
            retransmissions=stat_data.get("retransmissions", 0.0),
            timeout_errors=stat_data.get("timeout_errors", 0.0),
            avg_rtt=rtt_data.get("avg", 0.0),
            min_rtt=rtt_data.get("min", 0.0),
            max_rtt=rtt_data.get("max", 0.0),
            sip_response_jitter=rtt_data.get("sip_response_jitter", 0.0),
            **rtp_data,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _build_sipp_command(
    sipp_bin: str,
    target_url: str,
    number_of_calls: int,
    call_duration: int,
    media_type: str,
    transport: str,
    stat_file: str,
) -> list[str]:
    """Build the SIPp command line arguments."""
    cmd = [sipp_bin, target_url]

    # Scenario selection
    scenario_path = _SCENARIO_MAP.get(media_type)
    if scenario_path is None:
        cmd.extend(["-sn", "uac"])
    else:
        cmd.extend(["-sf", str(scenario_path)])

    # RTP echo — makes the remote UAS echo RTP back so we capture
    # bidirectional media streams for proper inbound quality metrics.
    if media_type != "none":
        cmd.append("-rtp_echo")

    # Call parameters
    cmd.extend([
        "-m", str(number_of_calls),
        "-d", str(call_duration * 1000),  # convert seconds to ms
        "-t", _TRANSPORT_MAP.get(transport, "u1"),
    ])

    # Trace output
    # -stf sets stat file path; RTT file is auto-named <scenario>_<pid>_rtt.csv in cwd
    cmd.extend([
        "-trace_rtt",
        "-trace_stat",
        "-stf", stat_file,
        "-fd", "1",        # stat dump frequency: 1 second
        "-rtt_freq", "1",  # dump RTT for every call (default is 200)
    ])

    # Non-interactive flags
    cmd.extend([
        "-nd",            # no ncurses display
        "-nostdin",       # no interactive input
    ])

    return cmd


def _needs_sudo() -> bool:
    """Check if we're on WSL where file capabilities (setcap) don't work."""
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


def _run_sipp(cmd: list[str], timeout: int, cwd: str = None) -> None:
    """Execute the SIPp command, using sudo on WSL where capabilities are ignored."""
    if _needs_sudo() and os.geteuid() != 0:
        cmd = ["sudo"] + cmd
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        if result.returncode != 0 and result.stderr:
            log_error("voip_sipp", "_run_sipp", Exception(f"SIPp non-zero exit: {result.stderr.strip()}"), context=f"cmd={cmd[0]}")
    except subprocess.TimeoutExpired as e:
        log_error("voip_sipp", "_run_sipp", e, context=f"timeout={timeout}s")
    except FileNotFoundError:
        log_error("voip_sipp", "_run_sipp", FileNotFoundError(f"SIPp binary not found at: {cmd[0]}"))
        raise FileNotFoundError(f"SIPp binary not found at: {cmd[0]}")


def _find_trace_file(tmp_dir: str, pattern: str) -> str:
    """Find a SIPp trace file matching a pattern in tmp_dir.

    SIPp names files like: <scenario>_<pid>_rtt.csv, or uses the -stf path directly.
    """
    import glob
    matches = glob.glob(os.path.join(tmp_dir, pattern))
    if matches:
        return matches[0]

    # Fallback path for error reporting
    return os.path.join(tmp_dir, pattern)


def _parse_trace_stat(filepath: str) -> dict:
    """
    Parse SIPp trace_stat CSV file and extract cumulative metrics
    from the last data row.

    Returns dict with keys: successful_calls, failed_calls,
    retransmissions, timeout_errors
    """
    result = {
        "successful_calls": 0.0,
        "failed_calls": 0.0,
        "retransmissions": 0.0,
        "timeout_errors": 0.0,
    }

    try:
        with open(filepath, "r") as f:
            lines = f.readlines()
    except FileNotFoundError as e:
        log_error("voip_sipp", "_parse_trace_stat", e, context=f"filepath={filepath}")
        result = {k: -1 for k in result}
        return result

    # Filter out comment/empty lines, keep header + data
    data_lines = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    if len(data_lines) < 2:
        return result

    header_line = data_lines[0]
    last_data_line = data_lines[-1]

    headers = [h.strip() for h in header_line.split(";")]
    values = [v.strip() for v in last_data_line.split(";")]

    if len(headers) != len(values):
        return result

    row = dict(zip(headers, values))

    result["successful_calls"] = _safe_float(row.get("SuccessfulCall(C)", "0"))
    result["failed_calls"] = _safe_float(row.get("FailedCall(C)", "0"))
    result["retransmissions"] = _safe_float(row.get("Retransmissions(C)", "0"))

    timeout = (
        _safe_float(row.get("FailedMaxUDPRetrans(C)", "0"))
        + _safe_float(row.get("FailedTcpConnect(C)", "0"))
    )
    result["timeout_errors"] = timeout

    return result


def _parse_trace_rtt(filepath: str) -> dict:
    """
    Parse SIPp trace_rtt CSV file and compute avg/min/max
    of ResponseTime(ms) column.

    Returns dict with keys: avg, min, max
    """
    result = {"avg": 0.0, "min": 0.0, "max": 0.0, "sip_response_jitter": 0.0}

    try:
        with open(filepath, "r") as f:
            lines = f.readlines()
    except FileNotFoundError as e:
        log_error("voip_sipp", "_parse_trace_rtt", e, context=f"filepath={filepath}")
        result = {k: -1 for k in result}
        return result

    data_lines = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    if len(data_lines) < 2:
        return result

    headers = [h.strip().lower() for h in data_lines[0].split(";")]
    rtt_col = None
    for i, h in enumerate(headers):
        if "response_time" in h or "responsetime" in h:
            rtt_col = i
            break

    if rtt_col is None:
        return result

    rtt_values = []
    for line in data_lines[1:]:
        fields = line.split(";")
        if rtt_col < len(fields):
            val = _safe_float(fields[rtt_col].strip())
            if val > 0:
                rtt_values.append(val)

    if not rtt_values:
        return result

    result["avg"] = sum(rtt_values) / len(rtt_values)
    result["min"] = min(rtt_values)
    result["max"] = max(rtt_values)

    if len(rtt_values) > 1:
        diffs = [abs(rtt_values[i + 1] - rtt_values[i]) for i in range(len(rtt_values) - 1)]
        result["sip_response_jitter"] = sum(diffs) / len(diffs)

    return result


# Audio codec payload type names used by tshark to identify audio streams
_AUDIO_CODECS = {"pcmu", "pcma", "g722", "g729", "g7221", "telephone-event", "gsm", "opus",
                 "ilbc", "speex", "amr", "silk"}
# Video codec payload type names
_VIDEO_CODECS = {"h264", "h265", "vp8", "vp9", "av1"}


def _find_tshark_binary() -> str | None:
    """Find tshark binary, return None if not available."""
    for path in ["/usr/bin/tshark", "/usr/local/bin/tshark"]:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return shutil.which("tshark")


def _start_rtp_capture(pcap_file: str, timeout: int) -> subprocess.Popen | None:
    """Start tshark to capture UDP traffic for RTP analysis.

    Runs as the current user — assumes dumpcap has ``cap_net_raw`` /
    ``cap_net_admin`` capabilities so non-root users can capture.
    Returns the tshark :class:`~subprocess.Popen` handle, or *None*
    if tshark is unavailable or capture fails immediately.
    """
    tshark = _find_tshark_binary()
    if not tshark:
        log_error("voip_sipp", "_start_rtp_capture", Exception("tshark not found"), context="RTP media metrics will not be available")
        return None

    # Capture all UDP — the media (RTP) destination IP from SDP negotiation
    # often differs from the SIP signaling IP, so a host-scoped BPF filter
    # would miss RTP traffic.  The rtp,streams analysis ignores non-RTP.
    cmd = [
        tshark, "-i", "any",
        "-f", "udp",
        "-a", f"duration:{timeout}",
        "-w", pcap_file,
        "-q",
    ]

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # Quick check: if the process exits immediately with an error, give up
        try:
            ret = proc.wait(timeout=2)
            if ret != 0:
                log_error("voip_sipp", "_start_rtp_capture",
                          Exception(f"tshark exited immediately with code {ret}"))
                return None
        except subprocess.TimeoutExpired:
            pass  # Still running — good
        return proc
    except (FileNotFoundError, PermissionError) as e:
        log_error("voip_sipp", "_start_rtp_capture", e)
        return None


def _stop_rtp_capture(proc: subprocess.Popen | None) -> None:
    """Gracefully stop a running tshark capture."""
    if proc is None:
        return
    try:
        # SIGINT makes tshark flush and write the pcap cleanly
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    except Exception:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except Exception:
            pass


def _parse_rtp_streams(pcap_file: str, media_type: str) -> dict:
    """
    Analyse a pcap file with ``tshark -z rtp,streams`` and return
    per-stream (audio / video) and aggregate media metrics.

    tshark outputs a table like::

        Src Addr  Port  Dest Addr  Port  SSRC       Payload  Pkts  Lost  MaxDelta  MaxJitter  MeanJitter  Problems
        10.0.0.1  5004  10.0.0.2   5004  0xABCD1234 g711U    500   2     30.12     2.34       1.12

    Returns a dict of field names matching VoIPSIPpResult RTP/media fields.
    """
    defaults = {
        "audio_rtp_packets": 0.0,
        "audio_rtp_packet_loss": 0.0,
        "audio_rtp_packet_loss_rate": 0.0,
        "audio_rtp_jitter": 0.0,
        "audio_rtp_bitrate_kbps": 0.0,
        "video_rtp_packets": 0.0,
        "video_rtp_packet_loss": 0.0,
        "video_rtp_packet_loss_rate": 0.0,
        "video_rtp_jitter": 0.0,
        "video_rtp_bitrate_kbps": 0.0,
        "jitter": 0.0,
        "media_capture_available": 0.0,
        "media_streams_observed": 0.0,
        "media_packets_sent": 0.0,
        "media_packets_received": 0.0,
        "media_bytes_sent": 0.0,
        "media_bytes_received": 0.0,
        "media_packet_loss": 0.0,
        "media_packet_loss_rate": 0.0,
        "media_tx_bitrate_kbps": 0.0,
        "media_rx_bitrate_kbps": 0.0,
    }

    if not os.path.isfile(pcap_file):
        return defaults

    tshark = _find_tshark_binary()
    if not tshark:
        return defaults

    try:
        result = subprocess.run(
            [tshark, "-r", pcap_file, "-q", "-z", "rtp,streams"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            log_error("voip_sipp", "_parse_rtp_streams", Exception(f"tshark analysis failed: {result.stderr.strip()}"))
            return defaults
        output = result.stdout
    except Exception as e:
        log_error("voip_sipp", "_parse_rtp_streams", e)
        return defaults

    streams = _parse_rtp_stream_table(output)
    if not streams:
        defaults["media_capture_available"] = 1.0
        return defaults

    # Classify streams as audio or video by payload name
    audio_streams = []
    video_streams = []
    for s in streams:
        payload_lower = s["payload"].lower()
        if any(c in payload_lower for c in _VIDEO_CODECS):
            video_streams.append(s)
        elif any(c in payload_lower for c in _AUDIO_CODECS):
            audio_streams.append(s)
        else:
            # Heuristic: if media_type is video-only, treat unknown as video
            if media_type == "video":
                video_streams.append(s)
            else:
                audio_streams.append(s)

    metrics = dict(defaults)
    metrics["media_capture_available"] = 1.0
    metrics["media_streams_observed"] = float(len(streams))

    # Aggregate audio
    if audio_streams:
        total_pkts = sum(s["packets"] for s in audio_streams)
        total_lost = sum(s["lost"] for s in audio_streams)
        # Weighted mean jitter across audio streams
        weighted_jitter = sum(s["mean_jitter"] * s["packets"] for s in audio_streams)
        avg_jitter = weighted_jitter / total_pkts if total_pkts > 0 else 0.0
        metrics["audio_rtp_packets"] = float(total_pkts)
        metrics["audio_rtp_packet_loss"] = float(total_lost)
        metrics["audio_rtp_packet_loss_rate"] = total_lost / total_pkts if total_pkts > 0 else 0.0
        metrics["audio_rtp_jitter"] = avg_jitter
        # Bitrate: sum of per-stream bitrates
        metrics["audio_rtp_bitrate_kbps"] = sum(s.get("bitrate_kbps", 0.0) for s in audio_streams)

    # Aggregate video
    if video_streams:
        total_pkts = sum(s["packets"] for s in video_streams)
        total_lost = sum(s["lost"] for s in video_streams)
        weighted_jitter = sum(s["mean_jitter"] * s["packets"] for s in video_streams)
        avg_jitter = weighted_jitter / total_pkts if total_pkts > 0 else 0.0
        metrics["video_rtp_packets"] = float(total_pkts)
        metrics["video_rtp_packet_loss"] = float(total_lost)
        metrics["video_rtp_packet_loss_rate"] = total_lost / total_pkts if total_pkts > 0 else 0.0
        metrics["video_rtp_jitter"] = avg_jitter
        metrics["video_rtp_bitrate_kbps"] = sum(s.get("bitrate_kbps", 0.0) for s in video_streams)

    # Overall aggregates
    all_pkts = sum(s["packets"] for s in streams)
    all_lost = sum(s["lost"] for s in streams)
    metrics["media_packets_received"] = float(all_pkts)
    metrics["media_packets_sent"] = float(all_pkts)  # best estimate from one-sided capture
    metrics["media_packet_loss"] = float(all_lost)
    metrics["media_packet_loss_rate"] = all_lost / all_pkts if all_pkts > 0 else 0.0
    total_bytes = sum(s.get("bytes", 0) for s in streams)
    metrics["media_bytes_received"] = float(total_bytes)
    metrics["media_bytes_sent"] = float(total_bytes)
    total_bitrate = sum(s.get("bitrate_kbps", 0.0) for s in streams)
    metrics["media_rx_bitrate_kbps"] = total_bitrate
    metrics["media_tx_bitrate_kbps"] = total_bitrate

    # Overall jitter: weighted mean across all streams
    if all_pkts > 0:
        weighted = sum(s["mean_jitter"] * s["packets"] for s in streams)
        metrics["jitter"] = weighted / all_pkts

    return metrics


def _parse_rtp_stream_table(output: str) -> list[dict]:
    """
    Parse the ``tshark -z rtp,streams`` text table into a list of stream dicts.

    tshark 4.x output format (whitespace-separated, ``Lost`` column contains
    ``N (P%)`` which we handle)::

        StartTime  EndTime  SrcIP  Port  DstIP  Port  SSRC  Payload  Pkts  Lost (pct%)  MinDelta  MeanDelta  MaxDelta  MinJitter  MeanJitter  MaxJitter  Problems?

    Each returned dict has: src_addr, src_port, dst_addr, dst_port, ssrc,
    payload, packets, lost, mean_jitter, duration_s, bytes, bitrate_kbps.
    """
    streams = []
    in_table = False

    for line in output.splitlines():
        stripped = line.strip()

        # Detect start of data rows (after header line with column names)
        if "Payload" in stripped and "SSRC" in stripped:
            in_table = True
            continue

        # End-of-table separator
        if in_table and stripped.startswith("="):
            continue

        if not in_table or not stripped:
            continue

        parts = stripped.split()
        # Minimum expected tokens (some may be merged/split due to "(pct%)" in Lost)
        if len(parts) < 14:
            continue

        try:
            # Fixed positions: StartTime(0) EndTime(1) SrcIP(2) SrcPort(3)
            #                  DstIP(4) DstPort(5) SSRC(6) Payload(7) Pkts(8)
            start_time = float(parts[0])
            end_time = float(parts[1])
            src_addr = parts[2]
            src_port = int(parts[3])
            dst_addr = parts[4]
            dst_port = int(parts[5])
            ssrc = parts[6]
            payload = parts[7]
            packets = int(parts[8])

            # Lost column: either "N" or "N (P%)" — find the parenthesized
            # percentage token so we know where the remaining columns start.
            lost_idx = 9
            lost = int(parts[lost_idx])
            # Skip the "(P%)" token if present
            remaining_start = lost_idx + 1
            if remaining_start < len(parts) and parts[remaining_start].startswith("("):
                remaining_start += 1  # skip "(0.0%)" token

            rest = parts[remaining_start:]
            # rest should be: MinDelta MeanDelta MaxDelta MinJitter MeanJitter MaxJitter [Problems?]
            if len(rest) < 6:
                continue

            mean_jitter = float(rest[4])   # MeanJitter

            # Duration from start/end times
            duration_s = end_time - start_time if end_time > start_time else 0.0

            # Estimate bytes (tshark rtp,streams doesn't report bytes)
            payload_lower = payload.lower()
            if any(c in payload_lower for c in _VIDEO_CODECS):
                avg_pkt_size = 1200
            else:
                avg_pkt_size = 160  # typical G.711 payload
            bytes_total = packets * avg_pkt_size
            bitrate_kbps = (bytes_total * 8) / (duration_s * 1000) if duration_s > 0 else 0.0

            streams.append({
                "src_addr": src_addr,
                "src_port": src_port,
                "dst_addr": dst_addr,
                "dst_port": dst_port,
                "ssrc": ssrc,
                "payload": payload,
                "packets": packets,
                "lost": lost,
                "mean_jitter": mean_jitter,
                "duration_s": duration_s,
                "bytes": bytes_total,
                "bitrate_kbps": bitrate_kbps,
            })
        except (ValueError, IndexError) as e:
            log_error("voip_sipp", "_parse_rtp_stream_table", e, context=f"line={stripped}")
            continue

    return streams


def _safe_float(value: str) -> float:
    """Safely convert a string to float, returning -1 on failure."""
    try:
        return float(value)
    except (ValueError, TypeError) as e:
        log_error("voip_sipp", "_safe_float", e, context=f"value={value!r}")
        return -1


if __name__ == "__main__":
    params = {
        "target_url": ["20.219.59.36"],
        "number_of_calls": 5,
        "call_duration": 5,
        "type": "audio",
        "transport": "udp",
    }
    results = run_voip_sipp_test(parameters=params)
    for r in results:
        print(f"  call_success        : {r.call_success:.0f}")
        print(f"  call_setup_time     : {r.call_setup_time:.1f} ms")
        print(f"  failed_calls        : {r.failed_calls:.0f}")
        print(f"  retransmissions     : {r.retransmissions:.0f}")
        print(f"  timeout_errors      : {r.timeout_errors:.0f}")
        print(f"  avg_rtt             : {r.avg_rtt:.1f} ms")
        print(f"  min_rtt             : {r.min_rtt:.1f} ms")
        print(f"  max_rtt             : {r.max_rtt:.1f} ms")
        print(f"  sip_response_jitter : {r.sip_response_jitter:.1f} ms")
        print(f"  jitter (RTP)        : {r.jitter:.1f} ms")
        print(f"  media_capture       : {'yes' if r.media_capture_available else 'no'}")
        print(f"  media_streams       : {r.media_streams_observed:.0f}")
        if r.audio_rtp_packets > 0:
            print(f"  audio_rtp_packets   : {r.audio_rtp_packets:.0f}")
            print(f"  audio_rtp_loss      : {r.audio_rtp_packet_loss:.0f} ({r.audio_rtp_packet_loss_rate:.2%})")
            print(f"  audio_rtp_jitter    : {r.audio_rtp_jitter:.2f} ms")
            print(f"  audio_rtp_bitrate   : {r.audio_rtp_bitrate_kbps:.1f} kbps")
        if r.video_rtp_packets > 0:
            print(f"  video_rtp_packets   : {r.video_rtp_packets:.0f}")
            print(f"  video_rtp_loss      : {r.video_rtp_packet_loss:.0f} ({r.video_rtp_packet_loss_rate:.2%})")
            print(f"  video_rtp_jitter    : {r.video_rtp_jitter:.2f} ms")
            print(f"  video_rtp_bitrate   : {r.video_rtp_bitrate_kbps:.1f} kbps")
