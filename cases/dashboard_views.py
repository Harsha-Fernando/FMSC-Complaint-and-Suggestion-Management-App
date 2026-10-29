"""Dashboards, ageing report and management reports (Section 9, Wireframes 4, 6, 8)."""

import csv
from datetime import date

from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.models import User

from .forms import CaseFilterForm
from .models import (
    NOT_STARTED_STATUSES,
    RESOLVED_STATUSES,
    WORKING_STATUSES,
    Authority,
    Case,
    Status,
)
from .permissions import DASHBOARD_ROLES, role_required
from .view_helpers import paginate, querystring_without_page
from .dashboard_data import headline_counts, dashboard_data


def _filtered(request, base=None):
    form = CaseFilterForm(request.GET or None)
    queryset = base if base is not None else Case.objects.all()
    queryset = form.apply(queryset) if form.is_bound else queryset
    return form, queryset.select_related("category", "assigned_authority", "submitted_by")


def _average(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None




def authority_rows(cases):
    """Authority-wise pending cases (Wireframe 8 table)."""
    rows = []
    open_cases = cases.exclude(status__in=[Status.CLOSED, Status.REJECTED]).filter(
        assigned_authority__isnull=False
    )
    by_authority = {}
    for case in open_cases:
        by_authority.setdefault(case.assigned_authority_id, []).append(case)
    for authority in Authority.objects.all():
        items = by_authority.get(authority.pk, [])
        if not items and not authority.is_active:
            continue
        rows.append(
            {
                "authority": authority,
                "assigned": len(items),
                "in_progress": sum(1 for c in items if c.status in WORKING_STATUSES),
                "not_started": sum(1 for c in items if c.status in NOT_STARTED_STATUSES),
                "solved_waiting": sum(1 for c in items if c.status == Status.SOLVED),
                "urgent": sum(1 for c in items if c.priority == Case.Priority.URGENT),
                "average_age": _average([c.age_days for c in items]),
            }
        )
    rows.sort(key=lambda r: (-r["assigned"], r["authority"].name))
    return rows


@role_required(*DASHBOARD_ROLES)
def admin_dashboard(request):
    """Wireframe 4: counts, filters and the not-started ageing report."""
    form, cases = _filtered(request)
    counts = headline_counts(cases)
    ageing = sorted(
        cases.filter(status__in=NOT_STARTED_STATUSES),
        key=lambda c: (-c.age_days, c.priority != Case.Priority.URGENT),
    )
    waiting_review = cases.filter(status__in=[Status.SUBMITTED, Status.UNDER_REVIEW]).order_by(
        "-priority", "submitted_at"
    )
    solved_to_confirm = cases.filter(status=Status.SOLVED).order_by("solved_at")
    return render(
        request,
        "cases/dashboards/admin_dashboard.html",
        {
            "form": form,
            "counts": counts,
            "dashboard": dashboard_data(cases, counts=counts),
            "recent": cases.order_by("-submitted_at")[:5],
            "ageing": ageing[:50],
            "ageing_total": len(ageing),
            "waiting_review": waiting_review[:20],
            "solved_to_confirm": solved_to_confirm[:20],
            "qs": querystring_without_page(request),
        },
    )


@role_required(*DASHBOARD_ROLES)
def management_dashboard(request):
    """Wireframe 8: trends and authority performance for decision-making."""
    form, cases = _filtered(request)
    counts = headline_counts(cases)

    resolved = [c.resolution_days for c in cases.filter(status__in=RESOLVED_STATUSES)]
    decided = counts["total"] - counts["rejected"]
    resolution_rate = round(100 * (counts["solved"] + counts["closed"]) / decided) if decided else None

    categories = list(
        cases.values("category__name").annotate(n=Count("pk")).order_by("-n", "category__name")
    )
    top = categories[:8]
    peak = max((c["n"] for c in top), default=0)
    for item in top:
        item["pct"] = round(100 * item["n"] / peak) if peak else 0
        item["share"] = round(100 * item["n"] / counts["total"]) if counts["total"] else 0

    status_rows = []
    status_counts = dict(cases.values_list("status").annotate(n=Count("pk")))
    for value, label in Status.choices:
        status_rows.append({"status": value, "label": label, "n": status_counts.get(value, 0)})

    return render(
        request,
        "cases/dashboards/management_dashboard.html",
        {
            "form": form,
            "counts": counts,
            "dashboard": dashboard_data(cases, counts=counts),
            "resolution_rate": resolution_rate,
            "average_resolution": _average(resolved),
            "categories": top,
            "authority_rows": authority_rows(cases),
            "status_rows": status_rows,
        },
    )


@role_required(User.Role.AUTHORITY)
def authority_dashboard(request):
    """Wireframe 6: the authority's work queue."""
    user = request.user
    if user.authority is None:
        return render(request, "cases/dashboards/authority_dashboard.html", {"no_unit": True})
    mine = Case.objects.filter(assigned_authority=user.authority).select_related("category")
    today = timezone.localdate()
    month_start = date(today.year, today.month, 1)
    counts = mine.aggregate(
        assigned=Count("pk", filter=~Q(status__in=[Status.CLOSED, Status.REJECTED, Status.SOLVED])),
        urgent=Count(
            "pk",
            filter=Q(priority=Case.Priority.URGENT)
            & ~Q(status__in=[Status.CLOSED, Status.REJECTED, Status.SOLVED]),
        ),
        in_progress=Count("pk", filter=Q(status__in=WORKING_STATUSES)),
        solved_month=Count(
            "pk",
            filter=Q(status__in=RESOLVED_STATUSES, solved_at__date__gte=month_start)
            | Q(status=Status.CLOSED, closed_at__date__gte=month_start, solved_at__isnull=True),
        ),
    )
    active = sorted(
        mine.filter(status__in=list(NOT_STARTED_STATUSES - {Status.NOT_STARTED}) + list(WORKING_STATUSES)),
        key=lambda c: (c.priority != Case.Priority.URGENT, -c.age_days),
    )
    recent_done = mine.filter(status__in=RESOLVED_STATUSES).order_by("-solved_at", "-closed_at")[:8]
    return render(
        request,
        "cases/dashboards/authority_dashboard.html",
        {"authority": user.authority, "counts": counts, "active": active, "recent_done": recent_done,
         "dashboard": dashboard_data(mine, authority=True)},
    )


# ---------------------------------------------------------------------------
# Reports: filterable case list with CSV export (acceptance criterion 22)
# ---------------------------------------------------------------------------
REPORT_COLUMNS = [
    ("Case number", lambda c: c.case_number),
    ("Title", lambda c: c.title),
    ("Type", lambda c: c.get_case_type_display()),
    ("Priority", lambda c: c.get_priority_display()),
    ("Category", lambda c: c.category.name),
    ("Location", lambda c: c.location),
    ("Status", lambda c: c.get_status_display()),
    ("Assigned authority", lambda c: c.assigned_authority.name if c.assigned_authority else ""),
    ("Submitted by", lambda c: c.submitted_by.display_name),
    ("Reporter role", lambda c: c.submitted_by.get_role_display()),
    ("Submitted on", lambda c: timezone.localtime(c.submitted_at).strftime("%Y-%m-%d %H:%M")),
    ("Age in days", lambda c: c.age_days),
    ("Solved on", lambda c: timezone.localtime(c.solved_at).strftime("%Y-%m-%d") if c.solved_at else ""),
    ("Closed on", lambda c: timezone.localtime(c.closed_at).strftime("%Y-%m-%d") if c.closed_at else ""),
    ("Resolution days", lambda c: round(c.resolution_days, 1) if c.resolution_days is not None else ""),
]


def _csv_safe(value):
    """Stop spreadsheet formula injection from titles typed by users."""
    text = str(value)
    if text and text[0] in "=+-@\t\r":
        return "'" + text
    return text


@role_required(*DASHBOARD_ROLES)
def reports(request):
    form, cases = _filtered(request)
    allowed_sorts = {"submitted_at", "-submitted_at", "priority", "-priority", "status", "case_number"}
    sort_order = request.GET.get("sort", "-submitted_at")
    if sort_order not in allowed_sorts:
        sort_order = "-submitted_at"
    cases = cases.order_by(sort_order, "-submitted_at", "-pk")

    if request.GET.get("export") == "csv":
        stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="fmsc-cases-{stamp}.csv"'
        response.write("﻿")  # lets Excel open Sinhala/Tamil text correctly
        writer = csv.writer(response)
        writer.writerow([name for name, _ in REPORT_COLUMNS])
        for case in cases.iterator():
            writer.writerow([_csv_safe(get(case)) for _, get in REPORT_COLUMNS])
        return response

    counts = headline_counts(cases)
    by_category = cases.values("category__name").annotate(n=Count("pk")).order_by("-n")
    by_authority = (
        cases.values("assigned_authority__name").annotate(n=Count("pk")).order_by("-n")
    )
    params = request.GET.copy()
    params.pop("page", None)
    params["export"] = "csv"
    return render(
        request,
        "cases/dashboards/reports.html",
        {
            "form": form,
            "page": paginate(request, cases, per_page=25),
            "counts": counts,
            "by_category": by_category,
            "by_authority": by_authority,
            "sort_order": sort_order,
            "qs": querystring_without_page(request),
            "export_qs": params.urlencode(),
        },
    )
