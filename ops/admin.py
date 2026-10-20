import uuid

from django.conf import settings
from django.contrib import admin, messages
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from catalog.models import Market

from . import runner
from .models import JobRun


def start_tool(request, command, label=None, args=None, options=None):
    """Start a tool and send the admin to its live log. Used by the Tools page and admin actions."""
    if runner.already_running(command):
        messages.warning(request, f"“{runner.TOOLS[command]}” is already running — wait for it to finish.")
        return redirect("admin:ops_jobrun_changelist")
    job = runner.start(command, user=request.user, label=label, args=args, options=options)
    return redirect("admin:ops_jobrun_change", job.pk)


@admin.register(JobRun)
class JobRunAdmin(admin.ModelAdmin):
    """The changelist *is* the Tools page; each run's page shows its live log."""

    def get_urls(self):
        return [
            path("run/", self.admin_site.admin_view(self.run_view), name="ops_jobrun_run"),
            path("<int:pk>/log/", self.admin_site.admin_view(self.log_view), name="ops_jobrun_log"),
        ] + super().get_urls()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff

    def changelist_view(self, request, extra_context=None):
        runner.mark_stale_runs()
        context = {
            **self.admin_site.each_context(request),
            "title": "Admin tools",
            "opts": self.model._meta,
            "runs": JobRun.objects.select_related("started_by")[:15],
            "contact_ok": _contact_ok(),
            "stats": {
                "markets": Market.objects.count(),
                "unverified": Market.objects.filter(location_verified=False).count(),
                "no_photo": Market.objects.filter(image="").count(),
                "no_hotels": Market.objects.filter(hotels=None).count(),
            },
        }
        return TemplateResponse(request, "admin/ops/tools.html", context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        job = get_object_or_404(JobRun, pk=object_id)
        context = {**self.admin_site.each_context(request), "title": job.label, "opts": self.model._meta, "job": job}
        return TemplateResponse(request, "admin/ops/run.html", context)

    def log_view(self, request, pk):
        job = get_object_or_404(JobRun, pk=pk)
        return JsonResponse({"status": job.status, "label": job.get_status_display(), "log": job.log})

    def run_view(self, request):
        if request.method != "POST":
            return redirect("admin:ops_jobrun_changelist")
        tool = request.POST.get("tool")
        p = request.POST

        if tool == "geocode_markets":
            return start_tool(request, tool, options={"dry_run": p.get("dry_run") == "on",
                                                      **({"market": p["market"]} if p.get("market") else {})})
        if tool == "sync_hotels":
            opts = {}
            if p.get("market"):
                opts["market"] = p["market"]
            if p.get("radius", "").isdigit():
                opts["radius"] = int(p["radius"])
            return start_tool(request, tool, options=opts)
        if tool == "fetch_images":
            opts = {"force": p.get("force") == "on"}
            if p.get("only") in {"markets", "products", "categories"}:
                opts["only"] = p["only"]
            return start_tool(request, tool, options=opts)
        if tool == "import_markets":
            upload = request.FILES.get("csv_file")
            if not upload or not upload.name.lower().endswith(".csv"):
                messages.error(request, "Choose a .csv file to import.")
                return redirect("admin:ops_jobrun_changelist")
            name = default_storage.save(f"imports/{uuid.uuid4().hex}.csv", upload)
            return start_tool(request, tool, label=f"Import markets from {upload.name}",
                              args=[default_storage.path(name)])
        messages.error(request, "Unknown tool.")
        return redirect("admin:ops_jobrun_changelist")


def _contact_ok():
    email = (settings.OSM_CONTACT_EMAIL or "").strip()
    return email.count("@") == 1 and " " not in email and "example." not in email and "yourdomain" not in email


# --- Actions added to the Market / Product / Category admin pages ----------

def _ids(queryset):
    return ",".join(str(pk) for pk in queryset.values_list("pk", flat=True))


@admin.action(description="Find hotels near selected markets")
def find_hotels_action(modeladmin, request, queryset):
    return start_tool(request, "sync_hotels", label=f"Find hotels · {queryset.count()} market(s)",
                      options={"ids": _ids(queryset)})


@admin.action(description="Refine location of selected markets")
def geocode_action(modeladmin, request, queryset):
    return start_tool(request, "geocode_markets", label=f"Refine locations · {queryset.count()} market(s)",
                      options={"ids": _ids(queryset)})


def fetch_photos_action_for(only):
    @admin.action(description=f"Fetch photos for selected {only} (replaces existing)")
    def action(modeladmin, request, queryset):
        return start_tool(request, "fetch_images", label=f"Fetch photos · {queryset.count()} {only}",
                          options={"ids": _ids(queryset), "only": only, "force": True})
    action.__name__ = f"fetch_photos_{only}"
    return action
