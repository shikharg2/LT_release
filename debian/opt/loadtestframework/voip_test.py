#!/usr/bin/env python3
"""
VoIP integration test — runs all three SIPp scenarios (none, audio, video)
and verifies SIP signaling, RTP media flow, and pcap analysis.

Usage:
    python3 voip_test.py [TARGET_IP]

Default target: 20.219.59.36
"""

import sys
import time
from dataclasses import fields

from src.test_modules.voip_sipp import run_voip_sipp_test, VoIPSIPpResult

TARGET = sys.argv[1] if len(sys.argv) > 1 else "20.219.59.36"
NUM_CALLS = 3
CALL_DURATION = 5  # seconds

# ── Colour helpers ───────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ok(msg):
    print(f"  {GREEN}PASS{RESET}  {msg}")


def fail(msg):
    print(f"  {RED}FAIL{RESET}  {msg}")


def warn(msg):
    print(f"  {YELLOW}WARN{RESET}  {msg}")


def header(msg):
    print(f"\n{BOLD}{CYAN}{'=' * 60}")
    print(f"  {msg}")
    print(f"{'=' * 60}{RESET}")


# ── Assertion helpers ────────────────────────────────────────────────────
class Stats:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def check(self, condition, pass_msg, fail_msg):
        if condition:
            ok(pass_msg)
            self.passed += 1
        else:
            fail(fail_msg)
            self.failed += 1

    def advisory(self, condition, pass_msg, warn_msg):
        if condition:
            ok(pass_msg)
            self.passed += 1
        else:
            warn(warn_msg)
            self.warnings += 1


stats = Stats()


def print_result(r: VoIPSIPpResult):
    """Print all dataclass fields."""
    for f in fields(r):
        val = getattr(r, f.name)
        if isinstance(val, float):
            if val == int(val) and abs(val) < 1e9:
                print(f"    {f.name:30s} = {int(val)}")
            else:
                print(f"    {f.name:30s} = {val:.4f}")
        else:
            print(f"    {f.name:30s} = {val}")


# ── Scenario runners ────────────────────────────────────────────────────
def run_scenario(name: str, media_type: str) -> VoIPSIPpResult | None:
    header(f"Scenario: {name}  (type={media_type}, calls={NUM_CALLS}, "
           f"duration={CALL_DURATION}s, target={TARGET})")

    params = {
        "target_url": [TARGET],
        "number_of_calls": NUM_CALLS,
        "call_duration": CALL_DURATION,
        "type": media_type,
        "transport": "udp",
    }

    start = time.monotonic()
    results = run_voip_sipp_test(parameters=params)
    elapsed = time.monotonic() - start
    print(f"\n  Completed in {elapsed:.1f}s")

    if not results:
        fail(f"No results returned for {name}")
        stats.failed += 1
        return None

    r = results[0]
    print()
    print_result(r)
    print()
    return r


def verify_signaling(r: VoIPSIPpResult, label: str):
    """Verify SIP signaling is healthy."""
    print(f"  {BOLD}-- SIP signaling checks --{RESET}")

    stats.check(
        r.call_success == NUM_CALLS,
        f"{label}: All {NUM_CALLS} calls successful",
        f"{label}: Expected {NUM_CALLS} successful calls, got {r.call_success:.0f}",
    )
    stats.check(
        r.failed_calls == 0,
        f"{label}: No failed calls",
        f"{label}: {r.failed_calls:.0f} calls failed",
    )
    stats.check(
        r.retransmissions == 0,
        f"{label}: No SIP retransmissions",
        f"{label}: {r.retransmissions:.0f} retransmissions detected",
    )
    stats.check(
        r.timeout_errors == 0,
        f"{label}: No timeout errors",
        f"{label}: {r.timeout_errors:.0f} timeout errors",
    )
    stats.check(
        r.call_setup_time > 0,
        f"{label}: Call setup time measured ({r.call_setup_time:.1f} ms)",
        f"{label}: Call setup time is 0 — RTT not recorded",
    )
    stats.check(
        r.avg_rtt > 0,
        f"{label}: Avg RTT measured ({r.avg_rtt:.1f} ms)",
        f"{label}: Avg RTT is 0",
    )
    stats.advisory(
        r.avg_rtt < 500,
        f"{label}: RTT within acceptable range (<500 ms)",
        f"{label}: RTT is high ({r.avg_rtt:.1f} ms)",
    )
    stats.check(
        r.sip_response_jitter >= 0,
        f"{label}: SIP response jitter computed ({r.sip_response_jitter:.1f} ms)",
        f"{label}: SIP response jitter is negative",
    )


def verify_pcap_capture(r: VoIPSIPpResult, label: str):
    """Verify tshark pcap capture was operational."""
    print(f"  {BOLD}-- pcap capture checks --{RESET}")

    stats.check(
        r.media_capture_available == 1.0,
        f"{label}: tshark capture was available",
        f"{label}: tshark capture NOT available — media metrics missing",
    )


def verify_no_media(r: VoIPSIPpResult, label: str):
    """Verify that no RTP media was generated (for the 'none' scenario)."""
    print(f"  {BOLD}-- media absence checks --{RESET}")

    stats.check(
        r.audio_rtp_packets == 0,
        f"{label}: No audio RTP packets (expected for signaling-only)",
        f"{label}: Unexpected audio RTP packets ({r.audio_rtp_packets:.0f})",
    )
    stats.check(
        r.video_rtp_packets == 0,
        f"{label}: No video RTP packets (expected for signaling-only)",
        f"{label}: Unexpected video RTP packets ({r.video_rtp_packets:.0f})",
    )
    stats.check(
        r.jitter == 0.0,
        f"{label}: RTP jitter is 0 (no media)",
        f"{label}: Unexpected RTP jitter ({r.jitter:.2f} ms)",
    )


def verify_audio_media(r: VoIPSIPpResult, label: str):
    """Verify audio RTP streams are present and healthy."""
    print(f"  {BOLD}-- audio media checks --{RESET}")

    stats.check(
        r.media_streams_observed >= NUM_CALLS,
        f"{label}: RTP streams detected ({r.media_streams_observed:.0f} >= {NUM_CALLS})",
        f"{label}: Too few RTP streams ({r.media_streams_observed:.0f}, expected >= {NUM_CALLS})",
    )
    stats.check(
        r.audio_rtp_packets > 0,
        f"{label}: Audio RTP packets captured ({r.audio_rtp_packets:.0f})",
        f"{label}: No audio RTP packets captured",
    )
    stats.advisory(
        r.audio_rtp_packets >= NUM_CALLS * 100,
        f"{label}: Sufficient audio packets ({r.audio_rtp_packets:.0f} >= {NUM_CALLS * 100})",
        f"{label}: Low audio packet count ({r.audio_rtp_packets:.0f})",
    )
    stats.check(
        r.audio_rtp_packet_loss_rate < 0.05,
        f"{label}: Audio packet loss acceptable ({r.audio_rtp_packet_loss_rate:.2%})",
        f"{label}: Audio packet loss too high ({r.audio_rtp_packet_loss_rate:.2%})",
    )
    stats.check(
        r.audio_rtp_jitter >= 0,
        f"{label}: Audio RTP jitter measured ({r.audio_rtp_jitter:.2f} ms)",
        f"{label}: Audio RTP jitter is negative",
    )
    stats.advisory(
        r.audio_rtp_jitter < 50,
        f"{label}: Audio jitter within acceptable range (<50 ms)",
        f"{label}: Audio jitter is high ({r.audio_rtp_jitter:.2f} ms)",
    )
    stats.check(
        r.audio_rtp_bitrate_kbps > 0,
        f"{label}: Audio bitrate measured ({r.audio_rtp_bitrate_kbps:.1f} kbps)",
        f"{label}: Audio bitrate is 0",
    )
    stats.check(
        r.video_rtp_packets == 0,
        f"{label}: No video RTP in audio-only scenario",
        f"{label}: Unexpected video RTP packets ({r.video_rtp_packets:.0f})",
    )


def verify_video_media(r: VoIPSIPpResult, label: str):
    """Verify video RTP streams are present and healthy."""
    print(f"  {BOLD}-- video media checks --{RESET}")

    stats.check(
        r.media_streams_observed >= NUM_CALLS,
        f"{label}: RTP streams detected ({r.media_streams_observed:.0f} >= {NUM_CALLS})",
        f"{label}: Too few RTP streams ({r.media_streams_observed:.0f}, expected >= {NUM_CALLS})",
    )
    stats.check(
        r.video_rtp_packets > 0,
        f"{label}: Video RTP packets captured ({r.video_rtp_packets:.0f})",
        f"{label}: No video RTP packets captured",
    )
    stats.advisory(
        r.video_rtp_packets >= NUM_CALLS * 50,
        f"{label}: Sufficient video packets ({r.video_rtp_packets:.0f} >= {NUM_CALLS * 50})",
        f"{label}: Low video packet count ({r.video_rtp_packets:.0f})",
    )
    stats.check(
        r.video_rtp_packet_loss_rate < 0.05,
        f"{label}: Video packet loss acceptable ({r.video_rtp_packet_loss_rate:.2%})",
        f"{label}: Video packet loss too high ({r.video_rtp_packet_loss_rate:.2%})",
    )
    stats.check(
        r.video_rtp_jitter >= 0,
        f"{label}: Video RTP jitter measured ({r.video_rtp_jitter:.2f} ms)",
        f"{label}: Video RTP jitter is negative",
    )
    stats.advisory(
        r.video_rtp_jitter < 50,
        f"{label}: Video jitter within acceptable range (<50 ms)",
        f"{label}: Video jitter is high ({r.video_rtp_jitter:.2f} ms)",
    )
    stats.check(
        r.video_rtp_bitrate_kbps > 0,
        f"{label}: Video bitrate measured ({r.video_rtp_bitrate_kbps:.1f} kbps)",
        f"{label}: Video bitrate is 0",
    )
    stats.check(
        r.audio_rtp_packets == 0,
        f"{label}: No audio RTP in video-only scenario",
        f"{label}: Unexpected audio RTP packets ({r.audio_rtp_packets:.0f})",
    )


def verify_aggregate_media(r: VoIPSIPpResult, label: str):
    """Verify aggregate media metrics are consistent."""
    print(f"  {BOLD}-- aggregate media checks --{RESET}")

    total_typed = r.audio_rtp_packets + r.video_rtp_packets
    stats.check(
        r.media_packets_received > 0,
        f"{label}: Aggregate media_packets_received > 0 ({r.media_packets_received:.0f})",
        f"{label}: Aggregate media_packets_received is 0",
    )
    stats.check(
        r.jitter > 0,
        f"{label}: Aggregate RTP jitter > 0 ({r.jitter:.2f} ms)",
        f"{label}: Aggregate RTP jitter is 0",
    )
    stats.check(
        r.media_packet_loss_rate < 0.05,
        f"{label}: Overall loss rate acceptable ({r.media_packet_loss_rate:.2%})",
        f"{label}: Overall loss rate too high ({r.media_packet_loss_rate:.2%})",
    )
    stats.advisory(
        abs(r.media_packets_received - total_typed) < 1,
        f"{label}: Aggregate packets match per-type sum ({r.media_packets_received:.0f} == {total_typed:.0f})",
        f"{label}: Aggregate packets mismatch ({r.media_packets_received:.0f} vs {total_typed:.0f})",
    )


# ── Main ─────────────────────────────────────────────────────────────────
def main():
    print(f"{BOLD}VoIP Integration Test{RESET}")
    print(f"Target: {TARGET}   Calls: {NUM_CALLS}   Duration: {CALL_DURATION}s")

    total_start = time.monotonic()

    # ── 1. Signaling-only (no media) ─────────────────────────────────
    r_none = run_scenario("Signaling Only", "none")
    if r_none:
        verify_signaling(r_none, "none")
        verify_pcap_capture(r_none, "none")
        verify_no_media(r_none, "none")

    # ── 2. Audio ─────────────────────────────────────────────────────
    r_audio = run_scenario("Audio (PCMU)", "audio")
    if r_audio:
        verify_signaling(r_audio, "audio")
        verify_pcap_capture(r_audio, "audio")
        verify_audio_media(r_audio, "audio")
        verify_aggregate_media(r_audio, "audio")

    # ── 3. Video ─────────────────────────────────────────────────────
    r_video = run_scenario("Video (H264)", "video")
    if r_video:
        verify_signaling(r_video, "video")
        verify_pcap_capture(r_video, "video")
        verify_video_media(r_video, "video")
        verify_aggregate_media(r_video, "video")

    # ── Summary ──────────────────────────────────────────────────────
    elapsed = time.monotonic() - total_start
    header("Summary")
    print(f"  {GREEN}Passed  : {stats.passed}{RESET}")
    if stats.warnings:
        print(f"  {YELLOW}Warnings: {stats.warnings}{RESET}")
    if stats.failed:
        print(f"  {RED}Failed  : {stats.failed}{RESET}")
    else:
        print(f"  {RED}Failed  : 0{RESET}")
    print(f"  Total   : {stats.passed + stats.failed + stats.warnings}")
    print(f"  Time    : {elapsed:.1f}s")
    print()

    if stats.failed:
        print(f"{RED}{BOLD}RESULT: FAIL{RESET}")
        sys.exit(1)
    else:
        print(f"{GREEN}{BOLD}RESULT: PASS{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
