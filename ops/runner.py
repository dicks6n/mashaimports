"""Run management commands in a background thread and stream their output to a JobRun."""

import threading
from datetime import timedelta
import time
import traceback

from django.core.management import call_command
from django.db import close_old_connections, connection
from django.utils import timezone

from .models import JobRun

# Commands the admin is allowed to start, with a human label.
TOOLS = {
    "geocode_markets": "Refine market locations",
    "sync_hotels": "Find hotels near markets",
    "fetch_images": "Fetch photos",
    "import_markets": "Import markets from CSV",
}


class LiveLog:
    """File-like object: buffers command output and saves it to the JobRun every second or so."""

    def __init__(self, job_id):
        self.job_id = job_id
        self.parts = []
        self.last_flush = 0.0

    def write(self, text):
        self.parts.append(str(text))
        if time.monotonic() - self.last_flush > 1.0:
            self.flush()
        return len(text)

    def flush(self):
        self.last_flush = time.monotonic()
        JobRun.objects.filter(pk=self.job_id).update(log="".join(self.parts))

    def isatty(self):
        return False

    @property
    def text(self):
        return "".join(self.parts)


def already_running(command):
    return JobRun.objects.filter(command=command, status=JobRun.Status.RUNNING).exists()


def start(command, user=None, label=None, args=None, options=None):
    """Create a JobRun and run `command` in the background. Returns the JobRun."""
    if command not in TOOLS:
        raise ValueError(f"Unknown tool {command}")
    args, options = list(args or []), dict(options or {})
    job = JobRun.objects.create(
        command=command, label=label or TOOLS[command], started_by=user,
        args={"args": args, "options": options},
    )
    threading.Thread(target=_run, args=(job.pk, command, args, options), daemon=True).start()
    return job


def _run(job_id, command, args, options):
    close_old_connections()
    log = LiveLog(job_id)
    status = JobRun.Status.SUCCESS
    try:
        call_command(command, *args, stdout=log, stderr=log, no_color=True, **options)
    except SystemExit as exc:  # CommandError raised outside call_command's handling
        status = JobRun.Status.FAILED
        log.write(f"\nStopped (exit {exc.code}).\n")
    except Exception as exc:
        status = JobRun.Status.FAILED
        log.write(f"\n✗ {exc}\n")
        if not exc.__class__.__name__ == "CommandError":
            log.write(traceback.format_exc())
    finally:
        JobRun.objects.filter(pk=job_id).update(log=log.text, status=status, finished=timezone.now())
        connection.close()


def mark_stale_runs():
    """Runs left 'running' after a server restart can never finish — mark them failed."""
    cutoff = timezone.now() - timedelta(hours=6)
    JobRun.objects.filter(status=JobRun.Status.RUNNING, started__lt=cutoff).update(
        status=JobRun.Status.FAILED, finished=timezone.now()
    )
