







#!/usr/bin/env python3
"""
Configuration validator for load test scenarios.
Validates configuration files against allowed parameters and values.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from src.utils.unit_converter import (
    METRIC_CATEGORIES, SPEED_CONVERSIONS, TIME_CONVERSIONS, COUNT_CONVERSIONS
)


class ConfigValidator:
    """Validates load test configuration files."""

    VALID_PROTOCOLS = ["speed_test", "web_browsing", "streaming", "voip_sipp"]
    VALID_MODES = ["once", "recurring"]
    VALID_OPERATORS = ["lt", "lte", "gt", "gte", "eq", "neq"]
    VALID_SCOPES = ["per_iteration", "scenario"]
    VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]
    VALID_AGGREGATIONS = ["avg", "min", "max", "stddev"] + [f"p{i}" for i in range(1, 100)]
    VALID_UNITS = (
        list(SPEED_CONVERSIONS.keys()) +
        list(TIME_CONVERSIONS.keys()) +
        list(COUNT_CONVERSIONS.keys()) +
        ["code", "ratio"]
    )

    # Protocol-specific required and optional parameters
    PROTOCOL_PARAMS = {
        "speed_test": {
            "required": ["target_url"],
            "optional": {"duration": int},
            "target_url_format": "host:port",
            "constraints": {
                "duration": {"min": 1},
            },
        },
        "web_browsing": {
            "required": ["target_url"],
            "optional": {"headless": bool, "disable_cache": bool},
            "target_url_format": "url",
        },
        "streaming": {
            "required": ["server_url", "api_key", "item_ids"],
            "optional": {
                "headless": bool,
                "disable_cache": bool,
                "parallel_browsing": bool,
                "aggregate": bool,
            },
        },
        "voip_sipp": {
            "required": ["target_url"],
            "optional": {
                "transport": str,
                "type": str,
                "call_duration": int,
                "number_of_calls": int,
            },
            "target_url_format": "host",
            "constraints": {
                "call_duration": {"min": 1},
                "number_of_calls": {"min": 1},
                "transport": {"allowed": ["udp", "tcp"]},
                "type": {"allowed": ["none", "audio", "video"]},
            },
        },
    }

    # Valid units per category, derived from unit_converter conversion tables
    CATEGORY_VALID_UNITS = {
        "speed": list(SPEED_CONVERSIONS.keys()),
        "time": list(TIME_CONVERSIONS.keys()),
        "count": list(COUNT_CONVERSIONS.keys()) + ["code", "ratio"],
    }

    # Protocol-specific valid metrics
    PROTOCOL_METRICS = {
        "speed_test": [
            "download_speed", "upload_speed", "jitter", "latency"
        ],
        "web_browsing": [
            "page_load_time", "ttfb", "dom_content_loaded",
            "http_response_code", "resource_count", "redirect_count"
        ],
        "streaming": [
            "initial_buffer_time", "test_wall_seconds",
            "startup_latency_sec", "playback_seconds", "active_playback_seconds",
            "rebuffer_events", "rebuffer_ratio", "min_buffer", "max_buffer",
            "avg_buffer", "resolution_switches", "segments_fetched",
            "non_200_segments", "avg_segment_latency_sec", "max_segment_latency_sec",
            "est_bitrate_bps", "error_count",
            "download_speed", "upload_speed", "latency", "jitter"
        ],
        "voip_sipp": [
            "call_success", "call_setup_time", "failed_calls",
            "retransmissions", "timeout_errors",
            "avg_rtt", "min_rtt", "max_rtt",
            "sip_response_jitter",
            "audio_rtp_packets", "audio_rtp_packet_loss",
            "audio_rtp_packet_loss_rate", "audio_rtp_jitter",
            "audio_rtp_bitrate_kbps",
            "video_rtp_packets", "video_rtp_packet_loss",
            "video_rtp_packet_loss_rate", "video_rtp_jitter",
            "video_rtp_bitrate_kbps",
            "jitter", "media_capture_available", "media_streams_observed",
            "media_packets_sent", "media_packets_received",
            "media_bytes_sent", "media_bytes_received",
            "media_packet_loss", "media_packet_loss_rate",
            "media_tx_bitrate_kbps", "media_rx_bitrate_kbps",
        ],
    }

    # VoIP metrics restricted by media type
    _VOIP_AUDIO_ONLY = {
        "audio_rtp_packets", "audio_rtp_packet_loss",
        "audio_rtp_packet_loss_rate", "audio_rtp_jitter", "audio_rtp_bitrate_kbps",
    }
    _VOIP_VIDEO_ONLY = {
        "video_rtp_packets", "video_rtp_packet_loss",
        "video_rtp_packet_loss_rate", "video_rtp_jitter", "video_rtp_bitrate_kbps",
    }
    _VOIP_MEDIA_METRICS = {
        "jitter", "media_capture_available", "media_streams_observed",
        "media_packets_sent", "media_packets_received",
        "media_bytes_sent", "media_bytes_received",
        "media_packet_loss", "media_packet_loss_rate",
        "media_tx_bitrate_kbps", "media_rx_bitrate_kbps",
    } | _VOIP_AUDIO_ONLY | _VOIP_VIDEO_ONLY

    def validate(self, config: dict) -> list[str]:
        """
        Validate the entire configuration.

        Args:
            config: Configuration dictionary

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate global settings
        if "global_settings" in config:
            errors.extend(self._validate_global_settings(config["global_settings"]))
        else:
            errors.append("Missing required field: 'global_settings'")

        # Validate scenarios
        if "scenarios" not in config:
            errors.append("Missing required field: 'scenarios'")
            return errors

        scenarios = config["scenarios"]
        if not isinstance(scenarios, list):
            errors.append("'scenarios' must be an array")
            return errors

        # Check for unique scenario IDs
        scenario_ids = []
        for idx, scenario in enumerate(scenarios):
            scenario_id = scenario.get("id", "")
            if scenario_id:
                if scenario_id in scenario_ids:
                    errors.append(f"Scenario {idx}: Duplicate scenario ID '{scenario_id}'")
                scenario_ids.append(scenario_id)

            errors.extend(self._validate_scenario(scenario, idx))

        return errors

    def _validate_global_settings(self, settings: dict) -> list[str]:
        """Validate global_settings section."""
        errors = []

        if not isinstance(settings, dict):
            return ["'global_settings' must be an object"]

        # report_path is required
        if "report_path" not in settings:
            errors.append("global_settings: Missing required field 'report_path'")
        elif not isinstance(settings["report_path"], str):
            errors.append("global_settings: 'report_path' must be a string")

        # log_level is optional but must be valid if present
        if "log_level" in settings:
            if settings["log_level"] not in self.VALID_LOG_LEVELS:
                errors.append(
                    f"global_settings: Invalid 'log_level' '{settings['log_level']}'. "
                    f"Must be one of: {', '.join(self.VALID_LOG_LEVELS)}"
                )

        return errors

    def _validate_scenario(self, scenario: dict, index: int) -> list[str]:
        """Validate a single scenario."""
        errors = []
        prefix = f"Scenario {index}"

        if not isinstance(scenario, dict):
            return [f"{prefix}: Must be an object"]

        # Required fields
        required_fields = ["id", "enabled", "protocol", "schedule", "parameters", "expectations"]
        for field in required_fields:
            if field not in scenario:
                errors.append(f"{prefix}: Missing required field '{field}'")

        # Validate id
        if "id" in scenario:
            if not isinstance(scenario["id"], str) or not scenario["id"].strip():
                errors.append(f"{prefix}: 'id' must be a non-empty string")

        # Validate description (optional but must be non-empty string if present)
        if "description" in scenario:
            if not isinstance(scenario["description"], str) or not scenario["description"].strip():
                errors.append(f"{prefix}: 'description' must be a non-empty string")

        # Validate enabled
        if "enabled" in scenario:
            if not isinstance(scenario["enabled"], bool):
                errors.append(f"{prefix}: 'enabled' must be a boolean")
            elif not scenario["enabled"]:
                return errors

        # Validate protocol
        protocol = scenario.get("protocol")
        if protocol is not None:
            if protocol not in self.VALID_PROTOCOLS:
                errors.append(
                    f"{prefix}: Invalid protocol '{protocol}'. "
                    f"Must be one of: {', '.join(self.VALID_PROTOCOLS)}"
                )

        # Validate schedule
        if "schedule" in scenario:
            errors.extend(self._validate_schedule(scenario["schedule"], prefix))

        # Validate parameters (protocol-specific)
        if "parameters" in scenario and protocol in self.VALID_PROTOCOLS:
            errors.extend(self._validate_parameters(scenario["parameters"], protocol, prefix))

        # Validate expectations
        if "expectations" in scenario and protocol in self.VALID_PROTOCOLS:
            params = scenario.get("parameters", {})
            errors.extend(self._validate_expectations(scenario["expectations"], protocol, prefix, params))
        
        if protocol == "speed_test":
            schedule = scenario.get("schedule",{})
            parameters = scenario.get("parameters",{})
            mode = schedule.get("mode")

            if mode == "recurring":
                duration_seconds = parameters.get("duration",10)
                # Each speed test iteration runs 3 iperf3 tests (download, upload, UDP)
                # plus 2x sleep(5) and a ping latency measurement (~5s)
                estimated_test_time = duration_seconds * 3 + 15
                interval_minutes = schedule.get("interval_minutes",0)
                interval_seconds = interval_minutes * 60

                if interval_seconds > 0 and estimated_test_time >= interval_seconds:
                    errors.append(
                        f"{prefix}: speed test estimated execution time ({estimated_test_time}s = "
                        f"3x{duration_seconds}s + 15s overhead) must be less than "
                        f"interval ({interval_minutes}min = {interval_seconds}s) to avoid overlapping tests."
                    )

        # Check for unknown fields
        known_fields = {"id", "description", "enabled", "protocol", "schedule", "parameters", "expectations"}
        for field in scenario:
            if field not in known_fields:
                errors.append(f"{prefix}: Unknown field '{field}'")

        return errors

    def _validate_schedule(self, schedule: dict, prefix: str) -> list[str]:
        """Validate schedule section."""
        errors = []

        if not isinstance(schedule, dict):
            return [f"{prefix}: 'schedule' must be an object"]

        # Validate mode
        mode = schedule.get("mode")
        if mode is None:
            errors.append(f"{prefix}: schedule: Missing required field 'mode'")
        elif mode not in self.VALID_MODES:
            errors.append(
                f"{prefix}: schedule: Invalid mode '{mode}'. "
                f"Must be one of: {', '.join(self.VALID_MODES)}"
            )

        # Validate start_time
        start_time = schedule.get("start_time")
        if start_time is None:
            errors.append(f"{prefix}: schedule: Missing required field 'start_time'")
        elif start_time != "immediate":
            try:
                parsed_time = datetime.fromisoformat(start_time)
                # Treat naive datetimes as UTC
                if parsed_time.tzinfo is None:
                    parsed_time = parsed_time.replace(tzinfo=timezone.utc)
                if parsed_time <= datetime.now(timezone.utc):
                    errors.append(
                        f"{prefix}: schedule: 'start_time' ({start_time}) is in the past"
                    )
            except (ValueError, TypeError):
                errors.append(
                    f"{prefix}: schedule: 'start_time' must be 'immediate' or a valid ISO datetime"
                )

        # For recurring mode, interval_minutes and duration_hours are required
        if mode == "recurring":
            if "interval_minutes" not in schedule:
                errors.append(f"{prefix}: schedule: 'interval_minutes' required for recurring mode")
            elif not isinstance(schedule["interval_minutes"], (int, float)):
                errors.append(f"{prefix}: schedule: 'interval_minutes' must be a number")
            elif schedule["interval_minutes"] <= 0:
                errors.append(f"{prefix}: schedule: 'interval_minutes' must be > 0")

            if "duration_hours" not in schedule:
                errors.append(f"{prefix}: schedule: 'duration_hours' required for recurring mode")
            elif not isinstance(schedule["duration_hours"], (int, float)):
                errors.append(f"{prefix}: schedule: 'duration_hours' must be a number")
            elif schedule["duration_hours"] <= 0:
                errors.append(f"{prefix}: schedule: 'duration_hours' must be > 0")

            # Cross-validate: duration_hours must be greater than interval_minutes
            interval = schedule.get("interval_minutes", 0)
            duration_minutes = schedule.get("duration_hours", 0) * 60
            if isinstance(interval, (int, float)) and isinstance(duration_minutes, (int, float)):
                if interval > 0 and duration_minutes > 0 and duration_minutes <= interval:
                    errors.append(
                        f"{prefix}: schedule: 'duration_hours' ({schedule['duration_hours']}h = {duration_minutes:.1f}min) "
                        f"must be greater than 'interval_minutes' ({interval}min) to allow multiple test runs"
                    )

        return errors

    def _validate_parameters(self, parameters: dict, protocol: str, prefix: str) -> list[str]:
        """Validate protocol-specific parameters."""
        errors = []

        if not isinstance(parameters, dict):
            return [f"{prefix}: 'parameters' must be an object"]

        proto_config = self.PROTOCOL_PARAMS.get(protocol, {})
        required = proto_config.get("required", [])
        optional = proto_config.get("optional", {})
        url_format = proto_config.get("target_url_format", "url")

        # Check required parameters
        for param in required:
            if param not in parameters:
                errors.append(f"{prefix}: parameters: Missing required field '{param}'")

        # Validate target_url format
        if "target_url" in parameters:
            target_urls = parameters["target_url"]
            if not isinstance(target_urls, list):
                errors.append(f"{prefix}: parameters: 'target_url' must be an array")
            elif len(target_urls) == 0:
                errors.append(f"{prefix}: parameters: 'target_url' must not be empty")
            else:
                for i, url in enumerate(target_urls):
                    if not isinstance(url, str):
                        errors.append(f"{prefix}: parameters: target_url[{i}] must be a string")
                    elif url_format == "host:port":
                        if not re.match(r'^[\w.-]+:\d+$', url):
                            errors.append(
                                f"{prefix}: parameters: target_url[{i}] must be in 'host:port' format"
                            )
                    elif url_format == "host":
                        if not re.match(r'^[\w.-]+$', url):
                            errors.append(
                                f"{prefix}: parameters: target_url[{i}] must be a hostname or IP address"
                            )
                    elif url_format == "url":
                        if not url.startswith(("http://", "https://")):
                            errors.append(
                                f"{prefix}: parameters: target_url[{i}] must be a valid URL"
                            )

        # Validate streaming-specific parameters (Jellyfin)
        if protocol == "streaming":
            if "server_url" in parameters:
                srv = parameters["server_url"]
                if not isinstance(srv, str) or not srv.startswith(("http://", "https://")):
                    errors.append(f"{prefix}: parameters: 'server_url' must be a valid HTTP/HTTPS URL")

            if "api_key" in parameters:
                key = parameters["api_key"]
                if not isinstance(key, str) or not key.strip():
                    errors.append(f"{prefix}: parameters: 'api_key' must be a non-empty string")

            if "item_ids" in parameters:
                ids = parameters["item_ids"]
                if not isinstance(ids, list):
                    errors.append(f"{prefix}: parameters: 'item_ids' must be an array")
                elif len(ids) == 0:
                    errors.append(f"{prefix}: parameters: 'item_ids' must not be empty")
                else:
                    for i, item_id in enumerate(ids):
                        if not isinstance(item_id, str) or not item_id.strip():
                            errors.append(f"{prefix}: parameters: item_ids[{i}] must be a non-empty string")

        # Validate optional parameter types
        for param, expected_type in optional.items():
            if param in parameters:
                if not isinstance(parameters[param], expected_type):
                    errors.append(
                        f"{prefix}: parameters: '{param}' must be a {expected_type.__name__}"
                    )

        # Check for unknown parameters
        known_params = set(required) | set(optional.keys())
        for param in parameters:
            if param not in known_params:
                errors.append(
                    f"{prefix}: parameters: Unknown parameter '{param}' for protocol '{protocol}'"
                )

        # Validate parameter value constraints
        constraints = proto_config.get("constraints", {})
        for param, rules in constraints.items():
            if param not in parameters:
                continue
            value = parameters[param]

            if "min" in rules and isinstance(value, (int, float)):
                if value < rules["min"]:
                    errors.append(
                        f"{prefix}: parameters: '{param}' must be >= {rules['min']}, got {value}"
                    )

            if "allowed" in rules and isinstance(value, str):
                if value not in rules["allowed"]:
                    errors.append(
                        f"{prefix}: parameters: '{param}' must be one of: "
                        f"{', '.join(rules['allowed'])}. Got '{value}'"
                    )

        return errors

    def _validate_expectations(self, expectations: list, protocol: str,
                               prefix: str, params: dict | None = None) -> list[str]:
        """Validate expectations array."""
        errors = []

        if not isinstance(expectations, list):
            return [f"{prefix}: 'expectations' must be an array"]

        valid_metrics = self.PROTOCOL_METRICS.get(protocol, [])

        for idx, exp in enumerate(expectations):
            exp_prefix = f"{prefix}: expectations[{idx}]"

            if not isinstance(exp, dict):
                errors.append(f"{exp_prefix}: Must be an object")
                continue

            # Required fields
            required_fields = ["metric", "operator", "value", "unit", "aggregation", "evaluation_scope"]
            for field in required_fields:
                if field not in exp:
                    errors.append(f"{exp_prefix}: Missing required field '{field}'")

            # Validate metric
            metric = exp.get("metric")
            if metric is not None and valid_metrics and metric not in valid_metrics:
                errors.append(
                    f"{exp_prefix}: Invalid metric '{metric}' for protocol '{protocol}'. "
                    f"Valid metrics: {', '.join(valid_metrics)}"
                )

            # VoIP media-type validation: reject metrics incompatible with type
            if metric and protocol == "voip_sipp" and params:
                media_type = params.get("type", "none")
                if media_type == "none" and metric in self._VOIP_MEDIA_METRICS:
                    errors.append(
                        f"{exp_prefix}: Metric '{metric}' requires media type 'audio' or 'video', "
                        f"but type is 'none' (signaling only)"
                    )
                elif media_type == "audio" and metric in self._VOIP_VIDEO_ONLY:
                    errors.append(
                        f"{exp_prefix}: Metric '{metric}' requires type 'video', "
                        f"but type is 'audio'"
                    )
                elif media_type == "video" and metric in self._VOIP_AUDIO_ONLY:
                    errors.append(
                        f"{exp_prefix}: Metric '{metric}' requires type 'audio', "
                        f"but type is 'video'"
                    )

            # Validate operator
            operator = exp.get("operator")
            if operator is not None and operator not in self.VALID_OPERATORS:
                errors.append(
                    f"{exp_prefix}: Invalid operator '{operator}'. "
                    f"Must be one of: {', '.join(self.VALID_OPERATORS)}"
                )

            # Validate value
            value = exp.get("value")
            if value is not None and not isinstance(value, (int, float)):
                errors.append(f"{exp_prefix}: 'value' must be a number")

            # Validate unit
            unit = exp.get("unit")
            if unit is not None and unit not in self.VALID_UNITS:
                errors.append(
                    f"{exp_prefix}: Invalid unit '{unit}'. "
                    f"Must be one of: {', '.join(self.VALID_UNITS)}"
                )

            # Validate aggregation
            aggregation = exp.get("aggregation")
            if aggregation is not None and aggregation not in self.VALID_AGGREGATIONS:
                errors.append(
                    f"{exp_prefix}: Invalid aggregation '{aggregation}'. "
                    f"Must be one of: avg, min, max, stddev, or p1-p99"
                )

            # Validate evaluation_scope
            scope = exp.get("evaluation_scope")
            if scope is not None and scope not in self.VALID_SCOPES:
                errors.append(
                    f"{exp_prefix}: Invalid evaluation_scope '{scope}'. "
                    f"Must be one of: {', '.join(self.VALID_SCOPES)}"
                )

            # Validate metric-unit mapping via category from unit_converter
            if metric and unit and metric in METRIC_CATEGORIES:
                category = METRIC_CATEGORIES[metric]
                valid_units = self.CATEGORY_VALID_UNITS.get(category, [])
                if valid_units and unit not in valid_units:
                    errors.append(
                        f"{exp_prefix}: Unit '{unit}' is not valid for metric '{metric}' "
                        f"(category: {category}). Expected one of: {', '.join(valid_units)}"
                    )

            # Check for unknown fields
            known_fields = set(required_fields)
            for field in exp:
                if field not in known_fields:
                    errors.append(f"{exp_prefix}: Unknown field '{field}'")

        return errors


def validate_config_file(config_path: str) -> tuple[bool, list[str]]:
    """
    Validate a configuration file.

    Args:
        config_path: Path to the configuration JSON file

    Returns:
        Tuple of (is_valid, list of errors)
    """
    path = Path(config_path)

    if not path.exists():
        return False, [f"Configuration file not found: {config_path}"]

    try:
        with open(path, "r") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]

    validator = ConfigValidator()
    errors = validator.validate(config)

    return len(errors) == 0, errors


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m src.utils.config_validator <config_file>")
        sys.exit(1)

    config_path = sys.argv[1]
    is_valid, errors = validate_config_file(config_path)

    if is_valid:
        print(f"✓ Configuration is valid: {config_path}")
        sys.exit(0)
    else:
        print(f"✗ Configuration validation failed: {config_path}")
        print(f"\nFound {len(errors)} error(s):\n")
        for error in errors:
            print(f"  • {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
