from django.conf import settings
from django.db import models


class JobRun(models.Model):
    """One run of a maintenance command started from the admin Tools page."""

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCESS = "success", "Finished"
        FAILED = "failed", "Failed"

    command = models.CharField(max_length=60)
    label = models.CharField(max_length=160)
    args = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    log = models.TextField(blank=True)
    started_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    started = models.DateTimeField(auto_now_add=True)
    finished = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started"]
        verbose_name = "admin tool"
        verbose_name_plural = "admin tools"

    def __str__(self):
        return f"{self.label} · {self.get_status_display()}"

    @property
    def duration(self):
        if not self.finished:
            return None
        return int((self.finished - self.started).total_seconds())
