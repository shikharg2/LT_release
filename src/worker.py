#!/usr/bin/env python3
"""
Worker module that runs inside Docker containers.
Executes scheduled tests for a specific scenario.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from src.scheduler import ScenarioScheduler
from src.utils.error_logger import log_error, init_error_logger


def run_worker(scenario_id: str):
    """Run worker for a specific scenario."""
    # Get scenario config from environment
    scenario_config_str = os.getenv("SCENARIO_CONFIG")
    if not scenario_config_str:
        err = Exception(f"SCENARIO_CONFIG not set for scenario {scenario_id}")
        log_error("worker", "run_worker", err)
        print(f"Error: SCENARIO_CONFIG not set for scenario {scenario_id}")
        sys.exit(1)

    try:
        scenario_config = json.loads(scenario_config_str)
    except json.JSONDecodeError as e:
        log_error("worker", "run_worker", e, context=f"scenario_id={scenario_id}")
        print(f"Error: Invalid SCENARIO_CONFIG JSON for scenario {scenario_id}")
        sys.exit(1)

    # Initialize error logger in the results directory
    report_path = os.getenv("REPORT_PATH", "./results/")
    init_error_logger(report_path)

    print(f"Worker starting for scenario: {scenario_config.get('id', scenario_id)}")
    print(f"  Protocol: {scenario_config.get('protocol')}")
    print(f"  Hostname: {os.getenv('HOSTNAME', 'unknown')}")

    # Create scheduler and schedule the scenario
    scheduler = ScenarioScheduler()
    scheduler.schedule_scenario(scenario_id, scenario_config)
    scheduler.start()

    # Calculate end time
    schedule = scenario_config.get("schedule", {})
    mode = schedule.get("mode", "once")
    duration_hours = schedule.get("duration_hours", 1) 
    start_time = schedule.get("start_time","immediate")

    
    if start_time != "immediate":
        try:
            datetime.fromisoformat(start_time)
        except ValueError as e:
            log_error("worker", "run_worker", e, context=f"start_time={start_time}")
            raise ValueError("start_time string not in correct format.")
        
    
    if mode == "once" and start_time == "immediate":
        # Wait for single execution to complete
        print("Waiting for test execution to complete...")
        print(scenario_id)
        scheduler.wait_for_scenario(scenario_id,scenario_config=scenario_config)
        print("Test execution completed.")
    elif mode == "recurring" and start_time == "immediate":
        # Wait for full duration
        end_time = datetime.now(timezone.utc) + timedelta(hours=duration_hours) + timedelta(seconds=5) # Additional small buffer 
        while datetime.now(timezone.utc) <= end_time:
            if scheduler.is_scenario_complete(scenario_id):
                break
            time.sleep(10)
    elif mode == "once" and start_time != "immediate":
        next_run = datetime.fromisoformat(start_time).astimezone(timezone.utc)  # Time when the test will start
        delay = max(0, (next_run - datetime.now(timezone.utc)).total_seconds() - 1.0)

        if delay > 0:
            time.sleep(delay)
        print("Waiting for test execution to complete...")
        print(scenario_id)
        scheduler.wait_for_scenario(scenario_id,scenario_config=scenario_config)
        print("Test execution completed.")

    elif mode == "recurring" and start_time != "immediate":
        next_run = datetime.fromisoformat(start_time).astimezone(timezone.utc)
        delay = max(0, (next_run - datetime.now(timezone.utc)).total_seconds() - 1.0)

        if delay > 0:
            time.sleep(delay)
        end_time = next_run + timedelta(hours=duration_hours) + timedelta(seconds=5) # Additional small buffer 
        while datetime.now(timezone.utc) <= end_time:
            if scheduler.is_scenario_complete(scenario_id):
                break
            time.sleep(10)
    else:
        raise ValueError("Unknown mode or datetime config.")
    
    # Finalize
    scheduler.finalize_scenario(scenario_id)
    scheduler.shutdown()

    print(f"Worker completed for scenario: {scenario_id}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.worker <scenario_id>")
        sys.exit(1)

    scenario_id = sys.argv[1]
    run_worker(scenario_id)