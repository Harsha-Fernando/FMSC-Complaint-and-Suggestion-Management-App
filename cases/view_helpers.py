"""Shared case lookup, pagination, timeline and lifecycle presentation helpers."""

from django.utils.translation import gettext_lazy as gettext
from django.core.paginator import Paginator
from django.http import Http404

from .models import AuditLog, Case, Comment
from .permissions import can_see_internal


def get_visible_case(user, case_number):
    """Return the case if this user may see it.

    A case the user may not see gives 404 rather than 403, so case numbers
    belonging to other people cannot be probed.
    """
    try:
        return (
            Case.objects.visible_to(user)
            .select_related("category", "assigned_authority", "submitted_by")
            .get(case_number=case_number)
        )
    except Case.DoesNotExist as exc:
        raise Http404(gettext("Case not found")) from exc


def paginate(request, queryset, per_page=20):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("page"))


def querystring_without_page(request):
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()


def _actor_label(actor, viewer, case):
    if actor is None:
        return gettext("System")
    if actor.pk == viewer.pk:
        return gettext("You")
    if actor.pk == case.submitted_by_id:
        return actor.display_name if can_see_internal(viewer) else gettext("Reporter")
    if actor.is_authority_officer:
        unit = actor.authority.name if actor.authority else gettext("Authority")
        return f"{actor.display_name} ({unit})" if can_see_internal(viewer) else unit
    if actor.is_case_admin:
        return gettext("%(name)s (Administrator)") % {"name": actor.display_name} if can_see_internal(viewer) else gettext("Faculty office")
    return actor.display_name


def build_timeline(case, viewer):
    """Merge comments and audit entries into one history, oldest first.

    Reporters see their own submission, status changes and public comments.
    Staff see everything, including internal notes and field changes.
    """
    staff = can_see_internal(viewer)
    events = []

    comments = case.comments.select_related("added_by", "added_by__authority")
    if not staff:
        comments = comments.filter(is_internal=False)
    for comment in comments:
        events.append(
            {
                "when": comment.added_at,
                "who": _actor_label(comment.added_by, viewer, case),
                "kind": "comment",
                "type": comment.comment_type,
                "title": comment.get_comment_type_display(),
                "text": comment.text,
                "internal": comment.is_internal,
                "emphasis": comment.comment_type
                in {Comment.Type.INFO_REQUEST, Comment.Type.RESOLUTION, Comment.Type.REJECTION},
            }
        )

    audit = case.audit_logs.select_related("user", "user__authority").exclude(
        action=AuditLog.Action.COMMENT_ADDED
    )
    if not staff:
        audit = audit.filter(
            action__in=[AuditLog.Action.CREATED, AuditLog.Action.STATUS_CHANGED,
                        AuditLog.Action.ATTACHMENT_ADDED]
        )
    for entry in audit:
        text = ""
        if staff and entry.action == AuditLog.Action.FIELD_CHANGED and entry.field != "internal_note":
            text = f"{entry.old_value or '—'} → {entry.new_value or '—'}"
        events.append(
            {
                "when": entry.created_at,
                "who": _actor_label(entry.user, viewer, case),
                "kind": "audit",
                "type": entry.action,
                "title": entry.description or entry.get_action_display(),
                "text": text,
                "internal": False,
                "emphasis": False,
            }
        )

    events.sort(key=lambda e: (e["when"], 0 if e["kind"] == "audit" else 1))
    return events


LIFECYCLE_STEPS = [
    ("submitted", gettext("Submitted")),
    ("reviewed", gettext("Reviewed")),
    ("assigned", gettext("Assigned")),
    ("in_progress", gettext("In progress")),
    ("solved", gettext("Solved")),
    ("closed", gettext("Closed")),
]

STATUS_STEP = {
    "submitted": 0,
    "under_review": 1,
    "not_started": 1,
    "rejected": 1,
    "assigned": 2,
    "reopened": 2,
    "in_progress": 3,
    "waiting_info": 3,
    "solved": 4,
    "closed": 5,
}


def lifecycle(case):
    """The progress rail on the case page: where this case is in Section 8."""
    current = STATUS_STEP.get(case.status, 0)
    steps = []
    for index, (key, label) in enumerate(LIFECYCLE_STEPS):
        if index < current:
            state = "done"
        elif index == current:
            state = "current"
        else:
            state = "todo"
        if index == current and case.status not in {"submitted", "assigned", "in_progress",
                                                     "solved", "closed"}:
            label = case.get_status_display()
        if case.status == "rejected":
            if index == current:
                state = "stopped"
            elif index > current:
                state = "skipped"
        steps.append({"label": label, "state": state, "number": index + 1})
    return steps
