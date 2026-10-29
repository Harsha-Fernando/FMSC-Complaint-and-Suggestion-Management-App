from django.utils.translation import gettext_lazy as gettext
from django.utils.translation import override
from functools import lru_cache

from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse


@lru_cache(maxsize=4)
def _logo_url(path):
    """Static URL of a logo file, or None if it has not been added yet."""
    if path and finders.find(path):
        return static(path)
    return None


def branding():
    return {
        "university_logo": _logo_url(settings.UNIVERSITY_LOGO),
        "faculty_logo": _logo_url(settings.FACULTY_LOGO),
    }


def app_context(request):
    """Logos, navigation and unread-notification count for every page."""
    context = branding()
    # Django get_available_languages translates names into the active language.
    # Keep the configured native names recognizable in every language.
    context["language_options"] = settings.LANGUAGES
    match = getattr(request, "resolver_match", None)
    case_number = match.kwargs.get("case_number") if match else None
    context["language_next"] = reverse("cases:detail", args=[case_number]) if request.method == "POST" and case_number else request.get_full_path()
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return context

    nav = []
    if user.is_reporter:
        nav = [
            (gettext("Dashboard"), reverse("cases:home")),
            (gettext("Submit a case"), reverse("cases:create")),
            (gettext("My cases"), reverse("cases:my_cases")),
        ]
    elif user.is_authority_officer:
        nav = [(gettext("Work queue"), reverse("cases:authority_dashboard"))]
    elif user.is_management_viewer:
        nav = [
            (gettext("Overview"), reverse("cases:management_dashboard")),
            (gettext("Case dashboard"), reverse("cases:admin_dashboard")),
            (gettext("Reports"), reverse("cases:reports")),
        ]
    elif user.is_case_admin:
        nav = [
            (gettext("Dashboard"), reverse("cases:admin_dashboard")),
            (gettext("All cases"), reverse("cases:reports")),
            (gettext("Overview"), reverse("cases:management_dashboard")),
            (gettext("Authorities"), reverse("cases:authority_list")),
            (gettext("Categories"), reverse("cases:category_list")),
        ]
        if user.is_staff:
            nav.append((gettext("Users"), reverse("admin:index")))

    current = request.path
    nav_items = []
    best = max(
        (url for _, url in nav if current.startswith(url) and url != "/"),
        key=len,
        default="/" if current == "/" else None,
    )
    icons = {"Submit a case": "plus", "My cases": "cases",
             "Work queue": "cases", "Overview": "chart", "Case dashboard": "grid",
             "Reports": "cases", "Dashboard": "grid", "All cases": "cases",
             "Authorities": "building", "Categories": "category", "Users": "users"}
    for label, url in nav:
        nav_items.append({"label": label, "url": url, "active": url == best,
                          "icon": _navigation_icon(label, icons), "group_start": _navigation_key(label) == "Authorities"})

    context.update(
        nav_items=nav_items,
        unread_count=user.notifications.filter(is_read=False).count(),
    )
    return context


def _navigation_key(label):
    with override("en"):
        return str(label)


def _navigation_icon(label, icons):
    return icons[_navigation_key(label)]
