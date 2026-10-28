"""Home, case submission, case pages and every action taken on a case."""

from django.utils.translation import gettext_lazy as gettext
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User

from .forms import (
    AdminReviewForm,
    AdminSolveForm,
    CaseSubmissionForm,
    CloseForm,
    FeedbackForm,
    ProgressUpdateForm,
    RejectForm,
    ReopenForm,
    ReplyForm,
)
from .models import (
    ASSIGNABLE_STATUSES,
    REJECTABLE_STATUSES,
    SOLVABLE_STATUSES,
    Attachment,
    Case,
    Status,
)
from .permissions import (
    CASE_ADMIN_ROLES,
    REPORTER_ROLES,
    can_see_internal,
    can_view_case,
    can_work_case,
    role_required,
)
from .dashboard_data import dashboard_data
from . import services
from .services import AUTHORITY_TRANSITIONS, WorkflowError
from .view_helpers import build_timeline, get_visible_case, lifecycle, paginate, querystring_without_page


@login_required
def home(request):
    user = request.user
    if user.is_reporter:
        return reporter_home(request)
    if user.is_authority_officer:
        return redirect("cases:authority_dashboard")
    if user.is_management_viewer:
        return redirect("cases:management_dashboard")
    if user.is_case_admin:
        return redirect("cases:admin_dashboard")
    raise PermissionDenied


# ---------------------------------------------------------------------------
# Student / lecturer (Wireframes 2 and 3)
# ---------------------------------------------------------------------------
def reporter_home(request):
    mine = Case.objects.filter(submitted_by=request.user)
    summary = mine.aggregate(
        submitted=Count("pk"),
        in_progress=Count(
            "pk", filter=~Q(status__in=[Status.SOLVED, Status.CLOSED, Status.REJECTED])
        ),
        solved=Count("pk", filter=Q(status__in=[Status.SOLVED, Status.CLOSED])),
        needs_reply=Count("pk", filter=Q(status=Status.WAITING_INFO)),
    )
    recent = mine.select_related("category")[:6]
    return render(request, "cases/reporter_home.html", {
        "summary": summary, "recent": recent,
        "dashboard": dashboard_data(mine, reporter=True),
        "latest_notice": request.user.notifications.filter(case__in=mine).select_related("case").first(),
    })


@role_required(*REPORTER_ROLES)
def case_create(request):
    if request.method == "POST":
        form = CaseSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            case = services.submit_case(request.user, form.cleaned_data, form.cleaned_data["files"])
            messages.success(
                request,
                gettext("Case %(value_0)s submitted. You will get a message here and by email when its status changes.") % {'value_0': case.case_number},
            )
            return redirect(case)
    else:
        initial = {}
        if request.GET.get("type") in Case.CaseType.values:
            initial["case_type"] = request.GET["type"]
        form = CaseSubmissionForm(initial=initial)
    return render(request, "cases/case_form.html", {"form": form})


@role_required(*REPORTER_ROLES)
def my_cases(request):
    view = request.GET.get("view", "all")
    cases = Case.objects.filter(submitted_by=request.user).select_related("category")
    if view == "open":
        cases = cases.exclude(status__in=[Status.SOLVED, Status.CLOSED, Status.REJECTED])
    elif view == "reply":
        cases = cases.filter(status=Status.WAITING_INFO)
    elif view == "done":
        cases = cases.filter(status__in=[Status.SOLVED, Status.CLOSED, Status.REJECTED])
    term = request.GET.get("q", "").strip()
    if term:
        cases = cases.filter(Q(case_number__icontains=term) | Q(title__icontains=term))
    return render(
        request,
        "cases/my_cases.html",
        {
            "page": paginate(request, cases),
            "view": view,
            "q": term,
            "qs": querystring_without_page(request),
        },
    )


# ---------------------------------------------------------------------------
# Case page: one URL, different panels depending on who is looking
# ---------------------------------------------------------------------------
def _case_context(request, case, **forms):
    user = request.user
    ctx = {
        "case": case,
        "steps": lifecycle(case),
        "timeline": build_timeline(case, user),
        "attachments": case.attachments.select_related("uploaded_by"),
        "staff_view": can_see_internal(user),
    }
    if user.is_case_admin:
        ctx.update(
            review_form=forms.get("review_form") or AdminReviewForm(case=case),
            reject_form=forms.get("reject_form") or RejectForm(),
            close_form=forms.get("close_form") or CloseForm(),
            reopen_form=forms.get("reopen_form") or ReopenForm(),
            solve_form=forms.get("solve_form") or AdminSolveForm(),
            can_review=case.status in services.ADMIN_REVIEWABLE_FROM,
            can_assign=case.status in ASSIGNABLE_STATUSES,
            can_reject=case.status in REJECTABLE_STATUSES,
            can_close=case.status == Status.SOLVED,
            can_reopen=case.status in {Status.SOLVED, Status.CLOSED} and case.assigned_authority_id,
            can_admin_solve=case.status in SOLVABLE_STATUSES,
            feedback_pending=case.status == Status.SOLVED
            and case.comments.filter(comment_type="feedback", added_at__gte=case.solved_at).exists(),
        )
    if can_work_case(user, case) and case.status in AUTHORITY_TRANSITIONS:
        ctx["progress_form"] = forms.get("progress_form") or ProgressUpdateForm(case=case)
    if case.submitted_by_id == user.pk:
        if case.status == Status.WAITING_INFO:
            ctx["reply_form"] = forms.get("reply_form") or ReplyForm()
            ctx["info_request"] = case.comments.filter(comment_type="info_request").last()
        if case.status == Status.SOLVED:
            ctx["feedback_form"] = forms.get("feedback_form") or FeedbackForm()
    return ctx


@login_required
def case_detail(request, case_number):
    case = get_visible_case(request.user, case_number)
    return render(request, "cases/case_detail.html", _case_context(request, case))


def _rerender(request, case, status=400, **forms):
    return render(request, "cases/case_detail.html", _case_context(request, case, **forms), status=status)


def _run(request, case, action, success_message, **forms):
    """Run a workflow action; show its error on the case page if it is not allowed."""
    try:
        action()
    except WorkflowError as exc:
        messages.error(request, str(exc))
        case.refresh_from_db()
        return _rerender(request, case, status=409, **forms)
    messages.success(request, success_message)
    return redirect(case)


# Reporter actions ------------------------------------------------------------
@require_POST
@role_required(*REPORTER_ROLES)
def case_reply(request, case_number):
    case = get_visible_case(request.user, case_number)
    if case.submitted_by_id != request.user.pk:
        raise Http404
    form = ReplyForm(request.POST, request.FILES)
    if not form.is_valid():
        return _rerender(request, case, reply_form=form)
    return _run(
        request, case,
        lambda: services.reporter_reply(case, request.user, form.cleaned_data["text"],
                                        form.cleaned_data["files"]),
        gettext("Reply sent. The case is back with the authority."),
        reply_form=form,
    )


@require_POST
@role_required(*REPORTER_ROLES)
def case_feedback(request, case_number):
    case = get_visible_case(request.user, case_number)
    if case.submitted_by_id != request.user.pk:
        raise Http404
    form = FeedbackForm(request.POST)
    if not form.is_valid():
        return _rerender(request, case, feedback_form=form)
    return _run(
        request, case,
        lambda: services.reporter_feedback(case, request.user, form.cleaned_data["text"]),
        gettext("Thanks. The faculty office will check the case and reopen it if needed."),
        feedback_form=form,
    )


# Administrator actions (Wireframe 5) -------------------------------------------
@require_POST
@role_required(*CASE_ADMIN_ROLES)
def admin_review(request, case_number):
    """Wireframe 5: save the review, or save it and assign in one step."""
    case = get_visible_case(request.user, case_number)
    action = "assign" if request.POST.get("action") == "assign" else "save"
    form = AdminReviewForm(request.POST, case=case, action=action)
    if not form.is_valid():
        return _rerender(request, case, review_form=form)
    data = form.cleaned_data

    if action == "assign":
        authority = data["authority"]
        verb = gettext("reassigned") if case.assigned_authority_id else gettext("assigned")

        def assign():
            with transaction.atomic():
                services.admin_save_review(
                    case, request.user, status=None, category=data["category"],
                    priority=data["priority"], internal_note=data["internal_note"],
                    auto_review=False,
                )
                services.assign_case(case, request.user, authority)

        return _run(request, case, assign, gettext("Case %(value_0)s to %(value_1)s. They have been notified.") % {'value_0': verb, 'value_1': authority},
                    review_form=form)

    def save():
        _, changed = services.admin_save_review(
            case, request.user,
            status=data.get("status"), category=data["category"],
            priority=data["priority"], internal_note=data["internal_note"],
        )
        if not changed:
            raise WorkflowError(gettext("No changes to save."))

    return _run(request, case, save, gettext("Changes saved."), review_form=form)


@require_POST
@role_required(*CASE_ADMIN_ROLES)
def admin_reject(request, case_number):
    case = get_visible_case(request.user, case_number)
    form = RejectForm(request.POST)
    if not form.is_valid():
        return _rerender(request, case, reject_form=form)
    return _run(
        request, case,
        lambda: services.reject_case(case, request.user, form.cleaned_data["reason"],
                                     form.cleaned_data["note"]),
        gettext("Case rejected. The reporter has been told why."),
        reject_form=form,
    )


@require_POST
@role_required(*CASE_ADMIN_ROLES)
def admin_close(request, case_number):
    case = get_visible_case(request.user, case_number)
    form = CloseForm(request.POST)
    if not form.is_valid():
        return _rerender(request, case, close_form=form)
    return _run(
        request, case,
        lambda: services.close_case(case, request.user, form.cleaned_data["note"]),
        gettext("Case closed."),
        close_form=form,
    )


@require_POST
@role_required(*CASE_ADMIN_ROLES)
def admin_reopen(request, case_number):
    case = get_visible_case(request.user, case_number)
    form = ReopenForm(request.POST)
    if not form.is_valid():
        return _rerender(request, case, reopen_form=form)
    return _run(
        request, case,
        lambda: services.reopen_case(case, request.user, form.cleaned_data["reason"]),
        gettext("Case reopened and sent back to the authority."),
        reopen_form=form,
    )


@require_POST
@role_required(*CASE_ADMIN_ROLES)
def admin_solve(request, case_number):
    case = get_visible_case(request.user, case_number)
    form = AdminSolveForm(request.POST)
    if not form.is_valid():
        return _rerender(request, case, solve_form=form)
    return _run(
        request, case,
        lambda: services.admin_mark_solved(case, request.user, form.cleaned_data["resolution_note"]),
        gettext("Case marked as solved. The reporter has been notified."),
        solve_form=form,
    )


# Authority action (Wireframe 7) ---------------------------------------------------
@require_POST
@role_required(User.Role.AUTHORITY)
def authority_update(request, case_number):
    case = get_visible_case(request.user, case_number)
    if not can_work_case(request.user, case):
        raise Http404
    form = ProgressUpdateForm(request.POST, request.FILES, case=case)
    if not form.is_valid():
        return _rerender(request, case, progress_form=form)
    data = form.cleaned_data
    new_status = data["new_status"]
    if new_status == Status.SOLVED:
        success = "Case marked as solved. The reporter has been notified."
    elif new_status == Status.WAITING_INFO and case.status != Status.WAITING_INFO:
        success = "Question sent to the reporter."
    else:
        success = "Progress saved."
    return _run(
        request, case,
        lambda: services.update_progress(
            case, request.user,
            new_status=new_status, comment=data["comment"], is_internal=data["is_internal"],
            resolution_note=data["resolution_note"], files=data["files"],
        ),
        success,
        progress_form=form,
    )


# ---------------------------------------------------------------------------
# Attachments: served only after a permission check (acceptance criterion 21)
# ---------------------------------------------------------------------------
@login_required
def attachment_download(request, pk):
    attachment = get_object_or_404(Attachment.objects.select_related("case"), pk=pk)
    if not can_view_case(request.user, attachment.case):
        raise Http404
    try:
        handle = attachment.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404(gettext("File missing")) from exc
    response = FileResponse(
        handle,
        content_type=attachment.content_type or "application/octet-stream",
        as_attachment=request.GET.get("download") == "1",
        filename=attachment.original_name,
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=3600"
    return response
