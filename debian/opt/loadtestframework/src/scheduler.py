import os
import uuid
import socket
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import EVENT_JOB_SUBMITTED, EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
from src.utils.db import insert_test_run, insert_raw_metrics_batch, insert_result_log
from src.utils.aggregator import get_aggregated_value, save_scenario_summary, parse_percentile_aggregation
from src.utils.unit_converter import normalize_for_comparison
from src.test_modules.speed_test import run_speed_test
from src.test_modules.web_browsing import run_web_browsing_test
from src.test_modules.streaming import run_streaming_test
from src.test_modules.voip_sipp import run_voip_sipp_test


PROTOCOL_HANDLERS = {
    "speed_test": run_speed_test,
    "web_browsing": run_web_browsing_test,
    "streaming": run_streaming_test,
    "voip_sipp": run_voip_sipp_test,
}


class ScenarioScheduler:
    def __init__(self):
        executors = {
            'default' : ThreadPoolExecutor(3)
        }
        # Configure scheduler with high misfire grace time to handle sequential job execution
        self.scheduler = BackgroundScheduler(
            timezone='UTC',
            job_defaults={
                'misfire_grace_time': 3600,  # 1 hour grace time
                # 'coalesce': True,  # Combine multiple missed runs into one
                'max_instances' : 3
            },
            executors=executors
        )
        
        self.scenario_jobs = {}  # scenario_id -> job_id mapping
        self.scenario_end_times = {}  # scenario_id -> end_time
        self.scenario_configs = {}  # scenario_id -> full config

        # Track running jobs per scenario
        self._running_jobs = {}  # scenario_id -> count of running jobs
        self._running_jobs_lock = threading.Lock()
        self.completion_events = {}

        # Register event listeners for job lifecycle tracking
        self.scheduler.add_listener(self._on_job_submitted, EVENT_JOB_SUBMITTED)
        self.scheduler.add_listener(
            self._on_job_finished,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED
        )

    def start(self):
        """Start the scheduler."""
        self.scheduler.start()

    def shutdown(self, wait: bool = True):
        """Shutdown the scheduler."""
        self.scheduler.shutdown(wait=wait)

    def _get_scenario_id_from_job_id(self, job_id: str) -> str | None:
        """Extract scenario_id from job_id (format: 'scenario_{scenario_id}')."""
        if job_id.startswith("scenario_"):
            return job_id[len("scenario_"):]
        return None

    def _on_job_submitted(self, event) -> None:
        """Called when a job starts executing."""
        scenario_id = self._get_scenario_id_from_job_id(event.job_id)
        if scenario_id is None:
            return
        with self._running_jobs_lock:
            self._running_jobs[scenario_id] = self._running_jobs.get(scenario_id, 0) + 1

    def _on_job_finished(self, event) -> None:
        """Called when a job finishes (success, error, or missed)."""
        scenario_id = self._get_scenario_id_from_job_id(event.job_id)
        if scenario_id is None:
            return
        with self._running_jobs_lock:
            if scenario_id in self._running_jobs:
                self._running_jobs[scenario_id] = max(0, self._running_jobs[scenario_id] - 1)

    def has_running_jobs(self, scenario_id: str) -> bool:
        """Check if a scenario has any jobs currently executing."""
        with self._running_jobs_lock:
            return self._running_jobs.get(scenario_id, 0) > 0
        
    def wait_for_scenario(self,scenario_id: str, scenario_config:dict,timeout: float = None) -> bool:
        """
        Wait for a scenario to complete.

        Args:
            scenario_id: The scenario to wait for
            timeout: Maximum time to wait in seconds (None = wait forever)
        
        Returns:
            True if scenario is completed, False if timeout occurred
        """
        event = self.completion_events.get(scenario_id)
        if event:
            return event.wait(timeout=timeout)
        return True
    

    def schedule_scenario(self, scenario_id: str, scenario_config: dict) -> None:
        """
        Schedule a scenario based on its configuration.
        """
        schedule = scenario_config.get("schedule", {})
        mode = schedule.get("mode", "once")
        start_time = schedule.get("start_time", "immediate")
        interval_minutes = schedule.get("interval_minutes", 10)
        duration_hours = schedule.get("duration_hours", 1)

        self.scenario_configs[scenario_id] = scenario_config
        self.completion_events[scenario_id] = threading.Event()

        # Calculate end time for recurring jobs
        if mode == "recurring":
            if start_time == "immediate":
                start_dt = datetime.now(timezone.utc)
            else:
                start_dt = datetime.fromisoformat(start_time).astimezone(timezone.utc)
            end_time = start_dt + timedelta(hours=duration_hours) + timedelta(seconds=5)
            self.scenario_end_times[scenario_id] = end_time #.replace(tzinfo=timezone.utc)

        # Create the job function
        job_func = self._create_job_function(scenario_id, scenario_config)

        if mode == "once":
            if start_time == "immediate":
                # Run immediately
                trigger = DateTrigger(run_date=(datetime.now(timezone.utc)+timedelta(seconds=5)))
            else:
                trigger = DateTrigger(run_date=datetime.fromisoformat(start_time).astimezone(timezone.utc))

            job = self.scheduler.add_job(
                job_func,
                trigger=trigger,
                id=f"scenario_{scenario_id}",
                name=f"Scenario {scenario_config.get('id', scenario_id)}",
            )
        else:  # recurring
            if start_time == "immediate":
                next_run = datetime.now(timezone.utc) + timedelta(seconds=5) # Added a time buffer for execution delay
            else:
                next_run = datetime.fromisoformat(start_time).astimezone(timezone.utc)

            trigger = IntervalTrigger(
                minutes=interval_minutes,
                start_date=next_run,
                end_date=self.scenario_end_times[scenario_id],
            )

            job = self.scheduler.add_job(
                job_func,
                trigger=trigger,
                id=f"scenario_{scenario_id}",
                name=f"Scenario {scenario_config.get('id', scenario_id)}",
            )

        self.scenario_jobs[scenario_id] = job.id

    def _create_job_function(self, scenario_id: str, scenario_config: dict) -> Callable:
        """Create a job function for the scenario."""

        def job_func():
            self._execute_test(scenario_id, scenario_config)

        return job_func

    def _execute_test(self, scenario_id: str, scenario_config: dict) -> None:
        """Execute a single test run for a scenario."""
        protocol = scenario_config.get("protocol")
        parameters = scenario_config.get("parameters", {})
        expectations = scenario_config.get("expectations", [])

        if protocol not in PROTOCOL_HANDLERS:
            print(f"Unknown protocol: {protocol}")
            return

        # Generate run_id and get worker node
        run_id = str(uuid.uuid4())
        worker_node = os.getenv("HOSTNAME", socket.gethostname())
        start_time = datetime.now(timezone.utc)

        # Insert test run
        insert_test_run(run_id, scenario_id, start_time, worker_node)

        # Execute the test
        handler = PROTOCOL_HANDLERS[protocol]
        results = handler(parameters)

        # Get configured metric names from expectations
        configured_metrics = self._get_configured_metrics(expectations)

        # Write metrics to database (only configured metrics)
        all_result_metrics = []
        for result in results:
            metrics = self._extract_metrics(result, configured_metrics)
            if metrics:
                insert_raw_metrics_batch(run_id, metrics)
                all_result_metrics.append(metrics)

        # Evaluate expectations for per_iteration scope
        self._evaluate_expectations(run_id, scenario_id, expectations, scope="per_iteration",
                                    result_metrics_list=all_result_metrics)

        if scenario_id not in self.scenario_end_times:
            event = self.completion_events.get(scenario_id)
            if event:
                event.set()

    def _get_configured_metrics(self, expectations: list) -> set[str]:
        """
        Extract the set of metric names from expectations configuration.

        Args:
            expectations: List of expectation dictionaries

        Returns:
            Set of metric names that should be stored
        """
        return {exp.get("metric") for exp in expectations if exp.get("metric")}

    def _extract_metrics(self, result, configured_metrics: set[str] | None = None) -> dict[str, float]:
        """
        Extract metrics from a test result object.

        Args:
            result: Test result (dataclass or dict)
            configured_metrics: Optional set of metric names to filter.
                               If None or empty, all metrics are returned.

        Returns:
            Dictionary of metric names to values
        """
        all_metrics = {}

        if hasattr(result, "__dataclass_fields__"):
            all_metrics = {field: getattr(result, field) for field in result.__dataclass_fields__
                          if isinstance(getattr(result, field), (int, float))}
        elif isinstance(result, dict):
            all_metrics = {k: v for k, v in result.items() if isinstance(v, (int, float))}

        # Filter to only configured metrics if specified
        if configured_metrics:
            return {k: v for k, v in all_metrics.items() if k in configured_metrics}

        return all_metrics

    def _evaluate_expectations(self, run_id: str, scenario_id: str,
                               expectations: list, scope: str,
                               result_metrics_list: list[dict] = None) -> None:
        """Evaluate expectations and write to results_log."""
        for expectation in expectations:
            if expectation.get("evaluation_scope") != scope:
                continue

            metric_name = expectation.get("metric")
            operator = expectation.get("operator")
            expected_value = expectation.get("value")
            expected_unit = expectation.get("unit", "")
            aggregation = expectation.get("aggregation", "avg")

            if scope == "per_iteration" and result_metrics_list:
                # Evaluate each result individually (per URL/server/video)
                for metrics in result_metrics_list:
                    measured_value = metrics.get(metric_name, 0)

                    # Check for error sentinel value
                    if measured_value == -1:
                        status = "ERROR"
                    else:
                        measured_normalized, expected_normalized = normalize_for_comparison(
                            measured_value, expected_value, expected_unit, metric_name
                        )
                        status = self._compare_values(measured_normalized, operator, expected_normalized)

                    insert_result_log(
                        run_id=run_id,
                        metric_name=metric_name,
                        expected_value=f"{expected_value} {expected_unit}",
                        measured_value=str(measured_value),
                        status=status,
                        scope=scope,
                    )
            else:
                # Scenario scope: aggregate from DB across all runs
                measured_value = get_aggregated_value(scenario_id, metric_name, aggregation)

                # Check for error sentinel value
                if measured_value == -1:
                    status = "ERROR"
                else:
                    measured_normalized, expected_normalized = normalize_for_comparison(
                        measured_value, expected_value, expected_unit, metric_name
                    )
                    status = self._compare_values(measured_normalized, operator, expected_normalized)

                insert_result_log(
                    run_id=run_id,
                    metric_name=metric_name,
                    expected_value=f"{expected_value} {expected_unit}",
                    measured_value=str(measured_value),
                    status=status,
                    scope=scope,
                )

    def _compare_values(self, measured: float, operator: str, expected: float) -> str:
        """Compare measured value against expected using operator."""
        comparisons = {
            "lte": measured <= expected,
            "lt": measured < expected,
            "gte": measured >= expected,
            "gt": measured > expected,
            "eq": measured == expected,
            "neq": measured != expected,
        }
        return "PASS" if comparisons.get(operator, False) else "FAIL"

    def finalize_scenario(self, scenario_id: str) -> None:
        """
        Finalize a scenario after all runs complete.
        Evaluates scenario-scope expectations and saves summary.
        """
        scenario_config = self.scenario_configs.get(scenario_id, {})
        expectations = scenario_config.get("expectations", [])

        # Get any run_id for this scenario to use for results_log
        from src.utils.db import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT run_id FROM load_test.test_runs WHERE scenario_id = %s LIMIT 1",
                    (scenario_id,)
                )
                row = cur.fetchone()
                run_id = row[0] if row else str(uuid.uuid4())

        # Evaluate scenario-scope expectations
        self._evaluate_expectations(run_id, scenario_id, expectations, scope="scenario")

        # Extract per-metric percentiles from expectations for summary storage
        metric_percentiles = {}
        for expectation in expectations:
            metric_name = expectation.get("metric")
            aggregation = expectation.get("aggregation", "")
            parsed_percentile = parse_percentile_aggregation(aggregation)
            if parsed_percentile is not None and metric_name:
                metric_percentiles[metric_name] = parsed_percentile

        # Save aggregated summary with per-metric percentiles
        save_scenario_summary(scenario_id, metric_percentiles=metric_percentiles)

    def is_scenario_complete(self, scenario_id: str) -> bool:
        """Check if a scenario has completed all its scheduled runs."""
        # If any jobs are still running, scenario is NOT complete
        if self.has_running_jobs(scenario_id):
            return False

        if scenario_id not in self.scenario_end_times:
            # One-time job, check if it has run
            job_id = self.scenario_jobs.get(scenario_id)
            if job_id:
                job = self.scheduler.get_job(job_id)
                return job is None or job.next_run_time is None
            return True

        # Recurring job: time must have elapsed AND no jobs running
        return datetime.now(timezone.utc) >= self.scenario_end_times[scenario_id]

    def get_pending_jobs(self) -> list:
        """Get list of pending jobs."""
        return self.scheduler.get_jobs()