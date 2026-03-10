#!/usr/bin/env python3
"""
Load Test Orchestrator

This module orchestrates load testing scenarios using Docker Swarm.
It reads configuration from main.json, manages PostgreSQL database,
schedules tests, and exports results.
"""

import json
import os
import subprocess
import time
import sys
import threading
from datetime import datetime, timedelta, timezone
import urllib.request
from src.utils.db import insert_scenario, export_tables_to_csv
from src.utils.uuid_generator import generate_uuid4
from src.utils.config_validator import validate_config_file
from src.utils.error_logger import log_error, init_error_logger


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""
    pass


CONFIG_PATH = "configurations/main.json"
DOCKER_IMAGE = "loadtest:latest"
DB_CONTAINER_NAME = "db-container"
DB_VOLUME_NAME = "load-test"


def load_config(config_path: str = CONFIG_PATH) -> dict:
    """Load configuration from main.json."""
    with open(config_path, "r") as f:
        return json.load(f)


def setup_report_path(config: dict) -> str:
    """Create and return the report path from configuration."""
    report_path = config.get("global_settings", {}).get("report_path", "./results/")
    os.makedirs(report_path, exist_ok=True)
    return report_path


def wait_for_postgres(max_retries: int = 30, delay: int = 2) -> bool:
    """Wait for PostgreSQL to be ready by attempting connections."""
    print("  Waiting for PostgreSQL to be ready...")
    for attempt in range(max_retries):
        result = subprocess.run(
            ["docker", "exec", DB_CONTAINER_NAME, "pg_isready", "-U", "postgres"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print(f"  PostgreSQL ready after {attempt * delay} seconds")
            return True
        time.sleep(delay)
    print("  Warning: PostgreSQL did not become ready in time")
    return False


def start_postgres_container() -> None:
    """Start PostgreSQL container with Docker volume."""
    # Create volume if not exists
    result = subprocess.run(
        ["docker", "volume", "create", DB_VOLUME_NAME],
        capture_output=True,
        text=True,
        timeout=30
    )
    if result.returncode != 0:
        print(f"  Warning: Failed to create volume: {result.stderr}")

    # Check if container already running
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={DB_CONTAINER_NAME}"],
        capture_output=True,
        text=True,
        timeout=30
    )

    if result.stdout.strip():
        print(f"  Container {DB_CONTAINER_NAME} already running")
        return

    # Remove stopped container if exists
    result = subprocess.run(
        ["docker", "rm", "-f", DB_CONTAINER_NAME],
        capture_output=True,
        text=True,
        timeout=30
    )
    if result.returncode != 0 and "No such container" not in result.stderr:
        print(f"  Warning: Failed to remove container: {result.stderr}")

    # Start PostgreSQL container
    subprocess.run([
        "docker", "run", "-d",
        "--name", DB_CONTAINER_NAME,
        "-e", "POSTGRES_PASSWORD=postgres",
        "-e", "POSTGRES_DB=postgres",
        "-v", f"{DB_VOLUME_NAME}:/var/lib/postgresql/data",
        "-p", "5432:5432",
        "--network", "loadtest-network",
        "-v", f"{os.path.abspath('docker/init_db.sql')}:/docker-entrypoint-initdb.d/init_db.sql",
        "postgres:16-alpine"
    ], check=True, timeout=60)

    # Wait for PostgreSQL to be ready using health check
    wait_for_postgres()


def ensure_docker_network() -> None:
    """Ensure Docker overlay network exists for Swarm service communication."""
    # Check if network already exists
    result = subprocess.run(
        ["docker", "network", "ls", "--filter", "name=loadtest-network", "--format", "{{.Name}}"],
        capture_output=True,
        text=True,
        timeout=30
    )

    if "loadtest-network" in result.stdout:
        print("  Network loadtest-network already exists")
        return

    # Create overlay network for Swarm services (attachable so regular containers can join)
    result = subprocess.run(
        ["docker", "network", "create", "--driver", "overlay", "--attachable", "loadtest-network"],
        capture_output=True,
        text=True,
        timeout=30
    )

    if result.returncode != 0:
        print(f"  Warning: Failed to create overlay network: {result.stderr}")
        # Fallback to bridge network for non-swarm mode
        print("  Attempting to create bridge network instead...")
        fallback_result = subprocess.run(
            ["docker", "network", "create", "loadtest-network"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if fallback_result.returncode != 0:
            raise RuntimeError(f"Failed to create network: {fallback_result.stderr}")
        print("  Created bridge network: loadtest-network")
    else:
        print("  Created overlay network: loadtest-network")


def init_docker_swarm() -> None:
    """Initialize Docker Swarm if not already active."""
    result = subprocess.run(
        ["docker", "info", "--format", "{{.Swarm.LocalNodeState}}"],
        capture_output=True,
        text=True,
        timeout=30
    )
    swarm_state = result.stdout.strip()
    print(f"  Swarm state: {swarm_state}")

    if swarm_state != "active":
        print("  Initializing Docker Swarm...")
        init_result = subprocess.run(
            ["docker", "swarm", "init", "--advertize-addr", "127.0.0.1"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if init_result.returncode != 0:
            print(f"  Warning: Swarm init failed: {init_result.stderr}")
        else:
            print("  Swarm initialized successfully")
    else:
        print("  Swarm already active")


def deploy_test_service(scenario_id: str, scenario_config: dict, replicas: int = 1,
                        report_path: str = "./results/") -> str:
    """
    Deploy a Docker Swarm service for running tests in parallel.
    Returns the service name.
    """
    service_name = f"loadtest-{scenario_id[:8]}"
    protocol = scenario_config.get("protocol", "unknown")

    # Environment variables for the container
    env_vars = [
        "-e", f"SCENARIO_ID={scenario_id}",
        "-e", f"SCENARIO_CONFIG={json.dumps(scenario_config)}",
        "-e", "DB_HOST=db-container",
        "-e", "DB_PORT=5432",
        "-e", "DB_NAME=postgres",
        "-e", "DB_USER=postgres",
        "-e", "DB_PASSWORD=postgres",
        "-e", f"REPORT_PATH={report_path}",
    ]

    cmd = [
        "docker", "service", "create",
        "--name", service_name,
        "--replicas", str(replicas),
        "--network", "loadtest-network",
        "--restart-condition", "none",
        "--cap-add", "NET_RAW",
        "--cap-add", "NET_ADMIN",
    ] + env_vars + [
        DOCKER_IMAGE,
        "python3", "-m", "src.worker", scenario_id
    ]

    subprocess.run(cmd, check=True, timeout=120)
    return service_name


def remove_service(service_name: str) -> None:
    """Remove a Docker Swarm service."""
    subprocess.run(
        ["docker", "service", "rm", service_name],
        capture_output=True,
        timeout=60
    )


def cleanup_exited_containers() -> None:
    """Remove exited containers created from the loadtest image."""
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"ancestor={DOCKER_IMAGE}", "--filter", "status=exited", "-q"],
        capture_output=True, text=True, timeout=30
    )
    container_ids = result.stdout.strip().split("\n")
    container_ids = [cid for cid in container_ids if cid]
    if container_ids:
        subprocess.run(["docker", "rm"] + container_ids, capture_output=True, timeout=30)


def check_running_services(active_services: list) -> list:
    """Check which services are still running."""
    running = []
    for service_name, scenario_id in active_services:
        result = subprocess.run(
            ["docker", "service", "ps", service_name, "--filter", "desired-state=running", "-q"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.stdout.strip():
            running.append((service_name, scenario_id))
    return running


def check_failed_services(active_services: list) -> list:
    """Check which services have failed tasks."""
    failed = []
    for service_name, scenario_id in active_services:
        result = subprocess.run(
            ["docker", "service", "ps", service_name, "--filter", "desired-state=shutdown", "--format", "{{.CurrentState}}"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if "Failed" in result.stdout or "Rejected" in result.stdout:
            failed.append((service_name, scenario_id))
    return failed


def get_video_runtime(server_url: str, api_key: str, item_id: str) -> timedelta:
    """Get video runtime from Jellyfin API. RunTimeTicks uses 10,000,000 ticks per second."""
    try:
        url = f"{server_url.rstrip('/')}/Items/{item_id}?api_key={api_key}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            runtime_ticks = data.get("RunTimeTicks", 0)
            runtime_seconds = runtime_ticks / 10_000_000
            return timedelta(seconds=runtime_seconds)
    except Exception as e:
        log_error("orchestrate", "get_video_runtime", e, context=f"item_id={item_id}")
        return timedelta(seconds=120)

def calculate_scenario_end_time(scenarios: list) -> datetime:
    """Calculate the absolute end time across all scenarios."""
    max_end_time = datetime.now(timezone.utc)
    for scenario in scenarios:
        if not scenario.get("enabled", False):
            continue
        schedule = scenario.get("schedule", {})
        start_time_raw = schedule["start_time"]
        if start_time_raw == "immediate":
            start_time = datetime.now(timezone.utc)
        else:
            start_time = datetime.fromisoformat(start_time_raw)
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            else:
                start_time = start_time.astimezone(timezone.utc)

        mode = schedule["mode"]
        if mode == "once":
            end_time = start_time
        elif mode == "recurring":
            duration_hours = float(schedule["duration_hours"])
            end_time = start_time + timedelta(hours=duration_hours)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        # Add protocol based durations (if any)
        protocol = scenario.get("protocol", "")
        if protocol == "":
            raise ValueError(f"Protocol field empty")

        if protocol == "speed_test":
            duration = (scenario.get("parameters", {}).get("duration", 0)) * 3
            end_time += timedelta(seconds=(duration+10))
        elif protocol == "streaming":
            params = scenario.get("parameters", {})
            server_url = params.get("server_url", "")
            api_key = params.get("api_key", "")
            item_ids = params.get("item_ids", [])
            for item_id in item_ids:
                vid_duration = get_video_runtime(server_url, api_key, item_id)
                end_time += vid_duration
        elif protocol == "web_browsing":
            urls = scenario.get("parameters", {}).get("target_url", [])
            end_time += timedelta(seconds=len(urls) * 30)
        elif protocol == "voip_sipp":
            params = scenario.get("parameters", {})
            num_calls = params.get("number_of_calls", 1)
            call_dur = params.get("call_duration", 5)
            num_targets = len(params.get("target_url", []))
            end_time += timedelta(seconds=(num_calls * call_dur + 60) * num_targets)

        max_end_time = max(max_end_time, end_time)

    return max_end_time


def periodic_export(report_path: str, stop_event: threading.Event, interval: int = 20) -> None:
    """Periodically export database tables to CSV in a background thread."""
    while not stop_event.is_set():
        try:
            export_tables_to_csv(report_path)
        except Exception as e:
            log_error("orchestrate", "periodic_export", e)
        stop_event.wait(interval)


def orchestrate(config_path: str = CONFIG_PATH):
    """Main orchestration function."""
    print("=" * 60)
    print("Load Test Orchestrator Starting")
    print("=" * 60)

    # # Step 1: Load and validate configuration
    print("\n[1/8] Loading and validating configuration...")
    is_valid, errors = validate_config_file(config_path)
    if not is_valid:
        print(f"  Configuration validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"    - {error}")
        raise ConfigurationError(f"Invalid configuration: {len(errors)} error(s) found")
    print("  Configuration is valid")
    config = load_config(config_path)
    
    # Step 2: Setup report path
    print("[2/8] Setting up report path...")
    report_path = setup_report_path(config)
    print(f"  Report path: {report_path}")

    # Initialize error logger to write into the results directory
    init_error_logger(report_path)

    # Step 3: Setup Docker infrastructure
    print("[3/8] Setting up Docker infrastructure...")
    init_docker_swarm()  # Must init swarm before creating overlay network
    ensure_docker_network()
    start_postgres_container()

    # Start periodic database export thread
    export_stop_event = threading.Event()
    export_thread = threading.Thread(
        target=periodic_export,
        args=(report_path, export_stop_event, 5),
        daemon=True
    )
    export_thread.start()
    print("  Started periodic database export (every 5 seconds)")
    
    # Step 4: Process enabled scenarios
    print("[4/8] Processing scenarios...")
    scenarios = config.get("scenarios", [])
    active_services = []
    scenario_ids = {}
    scenario_configs = {}  # Store configs for finalization

    for scenario in scenarios:
        if not scenario.get("enabled", False):
            print(f"  Skipping disabled scenario: {scenario.get('id', 'unknown')}")
            continue

        # Generate UUID for scenario
        scenario_id = generate_uuid4()
        scenario_ids[scenario.get("id")] = scenario_id
        scenario_configs[scenario_id] = scenario
        protocol = scenario.get("protocol", "unknown")

        print(f"  Processing scenario: {scenario.get('id')} ({protocol})")
        print(f"    UUID: {scenario_id}")

        # Step 5: Insert scenario into database
        insert_scenario(
            scenario_id=scenario_id,
            protocol=protocol,
            config_snapshot=scenario
        )
        
        # Deploy Docker Swarm service - worker handles scheduling and execution
        service_name = deploy_test_service(scenario_id, scenario, replicas=1, report_path=report_path)
        active_services.append((service_name, scenario_id))

    # Step 6: Wait for test execution
    print("[5/8] Waiting for workers to start...")

    scenario_end_time = calculate_scenario_end_time(scenarios)
    print(f"  Scenarios end at: {scenario_end_time.isoformat()}")
    
    # Monitor and wait for completion
    print("[6/8] Running tests...")
    end_time = scenario_end_time + timedelta(minutes=1)  # Add buffer to absolute end time
    try:
        while datetime.now(timezone.utc) <= end_time:
            running_services = check_running_services(active_services)
            failed_services = check_failed_services(active_services)

            if failed_services:
                print(f"\n  Warning: {len(failed_services)} service(s) failed:")
                for service_name, _ in failed_services:
                    print(f"    - {service_name}")

            # Exit if no services running (all completed or failed)
            if not running_services:
                if failed_services:
                    print("\n  All services stopped (some failed)")
                else:
                    print("\n  All services completed successfully")
                break

            print(f"  {len(running_services)} services running...", end="\r")
            time.sleep(10)
        else:
            print("  Test duration completed (timeout)")

    except KeyboardInterrupt:
        print("\n  Interrupted by user")

    # Step 7: Cleanup services (workers handle their own finalization)
    print("[7/8] Cleaning up services...")
    for service_name, _ in active_services:
        remove_service(service_name)
    cleanup_exited_containers()

    # Stop periodic export thread
    export_stop_event.set()
    export_thread.join(timeout=60)
    if export_thread.is_alive():
        print("  Warning: export thread did not stop in time")

    # Step 8: Export results to CSV (final export)
    print("[8/8] Exporting final results to CSV...")
    export_tables_to_csv(report_path)
    print(f"  Results exported to: {report_path}")

    print("\n" + "=" * 60)
    print("Orchestration Complete")
    print("=" * 60)


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else CONFIG_PATH
    orchestrate(config_path)
    
