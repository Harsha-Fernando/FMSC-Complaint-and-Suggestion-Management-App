"""Who may see and do what (Section 12: security and privacy)."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from accounts.models import User

Role = User.Role

REPORTER_ROLES = (Role.STUDENT, Role.LECTURER)
CASE_ADMIN_ROLES = (Role.ADMIN, Role.SYSADMIN)
DASHBOARD_ROLES = (Role.ADMIN, Role.SYSADMIN, Role.MANAGEMENT)


def role_required(*roles):
    """Allow the view only for users whose role is in `roles`."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def can_view_case(user, case):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.can_view_all_cases:
        return True
    if user.is_authority_officer:
        return user.authority_id is not None and case.assigned_authority_id == user.authority_id
    return case.submitted_by_id == user.pk


def can_see_internal(user):
    """Internal notes are for staff only, never the person who reported."""
    return user.is_case_admin or user.is_management_viewer or user.is_authority_officer


def can_work_case(user, case):
    """Authority officers may update cases assigned to their own unit."""
    return (
        user.is_authority_officer
        and user.authority_id is not None
        and case.assigned_authority_id == user.authority_id
    )
