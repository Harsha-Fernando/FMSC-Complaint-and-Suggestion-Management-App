from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Notification
from .permissions import can_view_case
from .view_helpers import paginate


@login_required
def notification_list(request):
    notes = request.user.notifications.select_related("case")
    return render(request, "cases/notifications.html", {"page": paginate(request, notes, 30)})


@require_POST
@login_required
def notification_open(request, pk):
    note = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not note.is_read:
        note.is_read = True
        note.save(update_fields=["is_read"])
    if note.case and can_view_case(request.user, note.case):
        return redirect(note.case)
    return redirect("cases:notifications")


@require_POST
@login_required
def notifications_mark_all_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect("cases:notifications")


@never_cache
@require_GET
@login_required
def notification_summary(request):
    """Only the signed-in user's unread count; never cached or shared."""
    return JsonResponse({"unread_count": request.user.notifications.filter(is_read=False).count()})
