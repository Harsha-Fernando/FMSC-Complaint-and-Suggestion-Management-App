from django import template
from django.utils.translation import gettext, ngettext
from django.template.defaultfilters import filesizeformat

register = template.Library()

# Status groups get one colour each, so a glance down a table shows where cases sit.
STATUS_TONE = {
    "submitted": "new",
    "under_review": "new",
    "not_started": "waiting",
    "assigned": "waiting",
    "reopened": "waiting",
    "in_progress": "active",
    "waiting_info": "attention",
    "solved": "done",
    "closed": "closed",
    "rejected": "rejected",
}


@register.inclusion_tag("partials/status.html")
def status_badge(case_or_status, label=None):
    status = getattr(case_or_status, "status", case_or_status)
    if label is None:
        label = (
            case_or_status.get_status_display()
            if hasattr(case_or_status, "get_status_display")
            else str(status).replace("_", " ").capitalize()
        )
    return {"tone": STATUS_TONE.get(status, "new"), "label": label}


@register.inclusion_tag("partials/priority.html")
def priority_badge(case):
    return {"urgent": case.priority == "urgent", "label": case.get_priority_display()}


@register.filter
def age_label(days):
    if days is None:
        return "—"
    if days == 0:
        return gettext("Today")
    if days == 1:
        return ngettext("%(count)s day", "%(count)s days", 1) % {"count": 1}
    return ngettext("%(count)s day", "%(count)s days", days) % {"count": days}


@register.filter
def age_tone(days):
    if days is None:
        return ""
    if days >= 7:
        return "age-old"
    if days >= 3:
        return "age-mid"
    return "age-new"


@register.filter
def filesize(value):
    return filesizeformat(value)


@register.simple_tag(takes_context=True)
def keep_params(context, **changes):
    """Rebuild the current query string with some values changed (for sort and page links)."""
    params = context["request"].GET.copy()
    for key, value in changes.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else "?"
