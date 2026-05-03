import json
import signal
import threading
import time

from redis import Redis

from daemon.agents import run_factory_brief, run_pipeline
from daemon.api import FactoryApi
from daemon.capabilities import detect_capabilities
from daemon.config import settings

shutdown = threading.Event()


def handle_shutdown(signum, frame) -> None:  # type: ignore[no-untyped-def]
    shutdown.set()


def heartbeat_loop(api: FactoryApi, worker_id: str, current_job: dict[str, str | None]) -> None:
    while not shutdown.is_set():
        try:
            api.heartbeat(worker_id, status="online", current_job_id=current_job.get("id"))
        except Exception as exc:
            print(f"heartbeat failed: {exc}")
        shutdown.wait(settings.worker_heartbeat_seconds)


def main() -> None:
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    api = FactoryApi()
    worker = api.register(detect_capabilities())
    worker_id = worker["id"]
    current_job: dict[str, str | None] = {"id": None}
    thread = threading.Thread(target=heartbeat_loop, args=(api, worker_id, current_job), daemon=True)
    thread.start()

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    print(f"worker {worker_id} listening on queues {settings.factory_brief_queue_name}, {settings.pipeline_queue_name}")

    while not shutdown.is_set():
        try:
            factory_state = api.factory_state()
            mode = factory_state.get("mode", "running")
            if mode != "running":
                api.heartbeat(worker_id, status=mode, current_job_id=None)
                shutdown.wait(3)
                continue
        except Exception as exc:
            print(f"factory state check failed: {exc}")

        item = redis.blpop([settings.factory_brief_queue_name, settings.pipeline_queue_name], timeout=5)
        if not item:
            continue
        queue_name, raw_payload = item
        payload = json.loads(raw_payload)
        if queue_name == settings.factory_brief_queue_name:
            brief_id = payload["factory_brief_id"]
            current_job["id"] = brief_id
            try:
                api.heartbeat(worker_id, status="busy", current_job_id=brief_id)
                run_factory_brief(api, brief_id)
            except Exception as exc:
                try:
                    api.set_factory_brief_status(brief_id, "failed")
                except Exception:
                    pass
                print(f"factory brief failed for {brief_id}: {exc}")
            finally:
                current_job["id"] = None
                api.heartbeat(worker_id, status="online", current_job_id=None)
            continue

        project_id = payload["project_id"]
        current_job["id"] = project_id
        try:
            api.heartbeat(worker_id, status="busy", current_job_id=project_id)
            run_pipeline(api, project_id)
        except Exception as exc:
            api.event(project_id, "pipeline", "Pipeline crashed", level="error", stderr=str(exc))
            print(f"pipeline failed for {project_id}: {exc}")
        finally:
            current_job["id"] = None
            api.heartbeat(worker_id, status="online", current_job_id=None)

    api.heartbeat(worker_id, status="offline", current_job_id=None)
    time.sleep(0.2)


if __name__ == "__main__":
    main()
