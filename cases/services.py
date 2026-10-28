"""The case workflow in one place.

Views stay thin: they validate input with a form and then call one function
here. Each function changes the case, writes the audit trail and sends the
notifications listed in Section 11, all inside one database transaction.
"""

from django.utils.translation import gettext_lazy as gettext
import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_noop, override
from .messages import SystemMessage, message

from accounts.models import User

from .models import (
    FINAL_STATUSES,
    ASSIGNABLE_STATUSES,
    REJECTABLE_STATUSES,
    SOLVABLE_STATUSES,
    Attachment,
    AuditLog,
    Case,
    Comment,
    Notification,
    Status,
)

logger = logging.getLogger("cases")


class WorkflowError(Exception):
    """Raised when an action is not allowed for the case's current status."""


# Statuses an authority may move a case to, keyed by the current status.
AUTHORITY_TRANSITIONS = {
    Status.ASSIGNED: [Status.IN_PROGRESS, Status.WAITING_INFO, Status.SOLVED],
    Status.REOPENED: [Status.IN_PROGRESS, Status.WAITING_INFO, Status.SOLVED],
    Status.IN_PROGRESS: [Status.IN_PROGRESS, Status.WAITING_INFO, Status.SOLVED],
    Status.WAITING_INFO: [Status.WAITING_INFO, Status.IN_PROGRESS, Status.SOLVED],
}

# Statuses the admin can set from the review form (assign/reject have their own buttons).
ADMIN_REVIEW_STATUSES = [Status.UNDER_REVIEW, Status.NOT_STARTED]
ADMIN_REVIEWABLE_FROM = {Status.SUBMITTED, Status.UNDER_REVIEW, Status.NOT_STARTED}


# ---------------------------------------------------------------------------
# Audit trail and notifications
# ---------------------------------------------------------------------------
def log_audit(case, user, action, description="", field="", old="", new=""):
    return AuditLog.objects.create(
        case=case,
        user=user,
        action=action,
        description=description[:255],
        field=field,
        old_value="" if old is None else str(old),
        new_value="" if new is None else str(new),
    )


def admin_users():
    admins = User.objects.filter(role=User.Role.ADMIN, is_active=True)
    if admins.exists():
        return admins
    return User.objects.filter(role=User.Role.SYSADMIN, is_active=True)


def authority_officers(authority):
    if authority is None:
        return User.objects.none()
    return User.objects.filter(role=User.Role.AUTHORITY, authority=authority, is_active=True)


def notify(recipients, case, notification_type, message, *, actor=None, extra_emails=()):
    """Create in-app notifications and send matching emails.

    The person who performed the action is not notified about their own action.
    Email failures are logged but never block the workflow.
    """
    seen = set()
    created = []
    for user in recipients:
        if user is None or user.pk in seen or (actor is not None and user.pk == actor.pk):
            continue
        seen.add(user.pk)
        created.append(
            Notification(
                case=case,
                recipient=user,
                notification_type=notification_type,
                message=(message.english() if isinstance(message, SystemMessage) else str(message))[:400],
                message_template=message.source if isinstance(message, SystemMessage) else "",
                message_parameters=message.parameters if isinstance(message, SystemMessage) else {},
            )
        )
    Notification.objects.bulk_create(created)

    if not settings.NOTIFY_BY_EMAIL:
        return created

    addresses = {n.recipient.email for n in created if n.recipient.email}
    addresses.update(e for e in extra_emails if e)
    if not addresses:
        return created

    message = message.english() if isinstance(message, SystemMessage) else str(message)
    subject = f"[{case.case_number}] {message}" if case else message
    link = f"{settings.SITE_URL.rstrip('/')}{case.get_absolute_url()}" if case else settings.SITE_URL
    with override("en"):
        email_status = case.get_status_display()
    body = (
        f"{message}\n\n"
        f"Case: {case.case_number} - {case.title}\n"
        f"Current status: {email_status}\n\n"
        f"Open the case: {link}\n\n"
        "This message was sent by the FMSC Complaint and Suggestion Management App."
    )

    def _send():
        delivered = set()
        for address in sorted(addresses):
            try:
                if send_mail(subject[:150], body, settings.DEFAULT_FROM_EMAIL, [address]):
                    delivered.add(address)
            except Exception:  # noqa: BLE001 - a mail outage must not lose the case update
                logger.exception("Could not email %s about %s", address, case)
        delivered_ids = [n.pk for n in created if n.pk and n.recipient.email in delivered]
        Notification.objects.filter(pk__in=delivered_ids).update(emailed=True)

    transaction.on_commit(_send)
    return created


STATUS_MESSAGES = {
    Status.UNDER_REVIEW: gettext_noop("Your case is being reviewed by the faculty office."),
    Status.NOT_STARTED: gettext_noop("Your case has been accepted and is waiting to be assigned."),
    Status.ASSIGNED: gettext_noop("Your case has been assigned to %(authority)s."),
    Status.IN_PROGRESS: gettext_noop("Work on your case is in progress."),
    Status.WAITING_INFO: gettext_noop("More information is needed on your case. Open it to reply."),
    Status.SOLVED: gettext_noop("Your case has been solved."),
    Status.CLOSED: gettext_noop("Your case has been closed."),
    Status.REJECTED: gettext_noop("Your case was not accepted."),
    Status.REOPENED: gettext_noop("Your case has been reopened and sent back for action."),
}


def _notify_reporter(case, actor, status, extra=""):
    source = STATUS_MESSAGES.get(status, gettext_noop("Your case is now %(status)s."))
    parameters = {"authority": case.assigned_authority or gettext("the relevant authority")} if status == Status.ASSIGNED else {}
    if status not in STATUS_MESSAGES:
        parameters["status"] = Status(status).label
    text = message(source, **parameters)
    if extra:
        text = message(gettext_noop("%(message)s %(extra)s"), message=text, extra=extra)
    ntype = Notification.Type.SOLVED if status == Status.SOLVED else Notification.Type.INFO_REQUEST if status == Status.WAITING_INFO else Notification.Type.STATUS_UPDATE
    notify([case.submitted_by], case, ntype, text, actor=actor)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _set_status(case, new_status, user, description=""):
    old_status = case.status
    if old_status == new_status:
        return False
    now = timezone.now()
    case.status = new_status
    if old_status == Status.SUBMITTED and case.reviewed_at is None:
        case.reviewed_at = now
    if new_status == Status.ASSIGNED:
        case.assigned_at = now
    if new_status == Status.IN_PROGRESS and case.started_at is None:
        case.started_at = now
    if new_status == Status.SOLVED:
        case.solved_at = now
    if new_status == Status.CLOSED:
        case.closed_at = now
    if new_status == Status.REOPENED:
        case.solved_at = None
        case.closed_at = None
    log_audit(
        case,
        user,
        AuditLog.Action.STATUS_CHANGED,
        description or f"Status changed to {Status(new_status).label}",
        field="status",
        old=Status(old_status).label,
        new=Status(new_status).label,
    )
    return True


def _add_comment(case, user, text, comment_type, is_internal=False):
    text = (text or "").strip()
    if not text:
        return None
    comment = Comment.objects.create(
        case=case, added_by=user, text=text, comment_type=comment_type, is_internal=is_internal
    )
    log_audit(
        case,
        user,
        AuditLog.Action.COMMENT_ADDED,
        f"{comment.get_comment_type_display()} added" + (" (internal)" if is_internal else ""),
        field="comment",
        new=text,
    )
    return comment


def add_attachments(case, user, files, kind=Attachment.Kind.EVIDENCE):
    """`files` is a list of (UploadedFile, file_type, content_type) from the form."""
    saved = []
    for uploaded, file_type, content_type in files:
        attachment = Attachment(
            case=case,
            original_name=uploaded.name[:255],
            file_type=file_type,
            kind=kind,
            size=uploaded.size,
            content_type=content_type,
            uploaded_by=user,
        )
        attachment.file.save(uploaded.name, uploaded, save=False)
        attachment.save()
        log_audit(
            case,
            user,
            AuditLog.Action.ATTACHMENT_ADDED,
            f"{attachment.get_kind_display()} uploaded: {attachment.original_name}",
            field="attachment",
            new=attachment.original_name,
        )
        saved.append(attachment)
    return saved


def _lock(case):
    """Re-read the case with a row lock so two people cannot update it at once."""
    return Case.objects.select_for_update().select_related(
        "assigned_authority", "submitted_by", "category"
    ).get(pk=case.pk)


# ---------------------------------------------------------------------------
# Reporter actions
# ---------------------------------------------------------------------------
@transaction.atomic
def submit_case(user, data, files):
    case = Case.objects.create(
        title=data["title"],
        description=data["description"],
        case_type=data["case_type"],
        priority=data["priority"],
        category=data["category"],
        location=data["location"],
        submitted_by=user,
        declaration_accepted=data["declaration"],
    )
    log_audit(case, user, AuditLog.Action.CREATED, f"{case.get_case_type_display()} submitted")
    add_attachments(case, user, files, kind=Attachment.Kind.EVIDENCE)
    notify(
        admin_users(), case, Notification.Type.NEW_CASE,
        message(gettext_noop("New case submitted: %(title)s"), title=case.title), actor=user,
    )
    return case


@transaction.atomic
def reporter_reply(case, user, text, files):
    case = _lock(case)
    if case.status != Status.WAITING_INFO:
        raise WorkflowError(gettext("You can reply only while the case is waiting for information."))
    _add_comment(case, user, text, Comment.Type.USER_REPLY)
    add_attachments(case, user, files, kind=Attachment.Kind.REPLY)
    _set_status(case, Status.IN_PROGRESS, user, "Reporter replied; case back in progress")
    case.save()
    notify(
        authority_officers(case.assigned_authority),
        case,
        Notification.Type.REPLY,
        message(gettext_noop("The reporter replied with the information you asked for: %(value_0)s"), value_0=case.title),
        actor=user,
    )
    return case


@transaction.atomic
def reporter_feedback(case, user, text):
    """The reporter says a solved case is not actually fixed; the admin decides."""
    case = _lock(case)
    if case.status != Status.SOLVED:
        raise WorkflowError(gettext("Feedback can be sent only on a solved case."))
    _add_comment(case, user, text, Comment.Type.FEEDBACK)
    notify(
        admin_users(),
        case,
        Notification.Type.FEEDBACK,
        message(gettext_noop("Reporter says the case is not resolved: %(value_0)s"), value_0=case.title),
        actor=user,
    )
    return case


# ---------------------------------------------------------------------------
# Administrator actions (Wireframe 5)
# ---------------------------------------------------------------------------
@transaction.atomic
def admin_save_review(case, user, *, status, category, priority, internal_note, auto_review=True):
    case = _lock(case)
    changed = []
    if status and status != case.status:
        if case.status not in ADMIN_REVIEWABLE_FROM or status not in ADMIN_REVIEW_STATUSES:
            raise WorkflowError(
                gettext("A case that is %(value_0)s cannot be moved to %(value_1)s from the review form.") % {'value_0': case.get_status_display().lower(), 'value_1': Status(status).label.lower()}
            )
        _set_status(case, status, user)
        changed.append("status")
    if category and category.pk != case.category_id:
        log_audit(
            case, user, AuditLog.Action.FIELD_CHANGED, "Category changed",
            field="category", old=case.category, new=category,
        )
        case.category = category
        changed.append("category")
    if priority and priority != case.priority:
        log_audit(
            case, user, AuditLog.Action.FIELD_CHANGED, "Priority changed",
            field="priority",
            old=Case.Priority(case.priority).label,
            new=Case.Priority(priority).label,
        )
        case.priority = priority
        changed.append("priority")
    note = (internal_note or "").strip()
    if note != case.internal_note.strip():
        log_audit(
            case, user, AuditLog.Action.FIELD_CHANGED, "Admin note for authority updated",
            field="internal_note", old=case.internal_note, new=note,
        )
        case.internal_note = note
        changed.append("internal_note")
    if auto_review and case.status == Status.SUBMITTED:
        # Saving the review form counts as starting the review.
        _set_status(case, Status.UNDER_REVIEW, user)
        changed.append("status")
    case.save()
    if "status" in changed:
        _notify_reporter(case, user, case.status)
    return case, changed


@transaction.atomic
def assign_case(case, user, authority, internal_note=None):
    case = _lock(case)
    if case.status not in ASSIGNABLE_STATUSES:
        raise WorkflowError(gettext("A %(value_0)s case cannot be assigned.") % {'value_0': case.get_status_display().lower()})
    if not authority.is_active:
        raise WorkflowError(gettext("%(value_0)s is inactive. Choose an active authority.") % {'value_0': authority})
    previous = case.assigned_authority
    if previous and previous.pk == authority.pk and case.status != Status.REOPENED:
        raise WorkflowError(gettext("This case is already assigned to %(value_0)s.") % {'value_0': authority})

    if internal_note is not None and internal_note.strip() != case.internal_note.strip():
        log_audit(
            case, user, AuditLog.Action.FIELD_CHANGED, "Admin note for authority updated",
            field="internal_note", old=case.internal_note, new=internal_note.strip(),
        )
        case.internal_note = internal_note.strip()

    case.assigned_authority = authority
    description = f"Reassigned from {previous} to {authority}" if previous else f"Assigned to {authority}"
    log_audit(
        case, user, AuditLog.Action.ASSIGNED, description,
        field="assigned_authority", old=previous or "", new=authority,
    )
    status_changed = _set_status(case, Status.ASSIGNED, user)
    if not status_changed:
        case.assigned_at = timezone.now()
    case.save()

    notify(
        authority_officers(authority),
        case,
        Notification.Type.ASSIGNED,
        message(gettext_noop("%(value_0)s assigned to %(value_1)s: %(value_2)s"), value_0=gettext('Urgent case') if case.priority == Case.Priority.URGENT else gettext('Case'), value_1=authority, value_2=case.title),
        actor=user,
        extra_emails=[authority.email],
    )
    if previous and previous.pk != authority.pk:
        notify(
            authority_officers(previous),
            case,
            Notification.Type.STATUS_UPDATE,
            message(gettext_noop("Case moved from %(value_0)s to %(value_1)s: %(value_2)s"), value_0=previous, value_1=authority, value_2=case.title),
            actor=user,
        )
    _notify_reporter(case, user, Status.ASSIGNED)
    return case


@transaction.atomic
def reject_case(case, user, reason, note):
    case = _lock(case)
    if case.status not in REJECTABLE_STATUSES:
        raise WorkflowError(gettext("A %(value_0)s case cannot be rejected.") % {'value_0': case.get_status_display().lower()})
    case.rejection_reason = reason
    reason_label = Case.RejectionReason(reason).label
    text = f"{reason_label}. {note.strip()}" if note and note.strip() else reason_label
    _add_comment(case, user, text, Comment.Type.REJECTION)
    _set_status(case, Status.REJECTED, user, f"Rejected: {reason_label}")
    case.save()
    _notify_reporter(case, user, Status.REJECTED, message(gettext_noop("Reason: %(value_0)s"), value_0=text))
    if case.assigned_authority:
        notify(
            authority_officers(case.assigned_authority),
            case,
            Notification.Type.STATUS_UPDATE,
            message(gettext_noop("Case withdrawn by the administrator: %(value_0)s"), value_0=case.title),
            actor=user,
        )
    return case


@transaction.atomic
def close_case(case, user, note=""):
    case = _lock(case)
    if case.status != Status.SOLVED:
        raise WorkflowError(gettext("Only a solved case can be closed."))
    _add_comment(case, user, note, Comment.Type.ADMIN_NOTE)
    _set_status(case, Status.CLOSED, user, "Closed after confirming completion")
    case.save()
    _notify_reporter(case, user, Status.CLOSED)
    return case


@transaction.atomic
def reopen_case(case, user, reason):
    case = _lock(case)
    if case.status not in {Status.SOLVED, Status.CLOSED}:
        raise WorkflowError(gettext("Only a solved or closed case can be reopened."))
    if not case.assigned_authority:
        raise WorkflowError(gettext("Assign an authority before reopening this case."))
    _add_comment(case, user, reason, Comment.Type.REOPEN)
    _set_status(case, Status.REOPENED, user, "Reopened: resolution not satisfactory")
    case.save()
    notify(
        authority_officers(case.assigned_authority),
        case,
        Notification.Type.ASSIGNED,
        message(gettext_noop("Case reopened and sent back to %(value_0)s: %(value_1)s"), value_0=case.assigned_authority, value_1=case.title),
        actor=user,
        extra_emails=[case.assigned_authority.email],
    )
    _notify_reporter(case, user, Status.REOPENED)
    return case


# ---------------------------------------------------------------------------
# Authority actions (Wireframe 7). Admins may also record a solution.
# ---------------------------------------------------------------------------
@transaction.atomic
def update_progress(case, user, *, new_status, comment, is_internal, resolution_note, files):
    case = _lock(case)
    allowed = AUTHORITY_TRANSITIONS.get(case.status)
    if allowed is None:
        raise WorkflowError(gettext("A %(value_0)s case cannot be updated.") % {'value_0': case.get_status_display().lower()})
    if new_status not in allowed and new_status != case.status:
        raise WorkflowError(
            gettext("A case cannot move from %(value_0)s to %(value_1)s.") % {'value_0': case.get_status_display().lower(), 'value_1': Status(new_status).label.lower()}
        )
    if new_status == Status.SOLVED and not (resolution_note or "").strip():
        # Acceptance criterion 17
        raise WorkflowError(gettext("Add a resolution note before marking the case as solved."))
    if new_status == Status.WAITING_INFO and case.status != Status.WAITING_INFO:
        if not (comment or "").strip():
            raise WorkflowError(gettext("Write what information you need before asking the reporter."))
        if is_internal:
            raise WorkflowError(gettext("An information request must be visible to the reporter."))

    comment_type = (
        Comment.Type.INFO_REQUEST
        if new_status == Status.WAITING_INFO and case.status != Status.WAITING_INFO
        else Comment.Type.PROGRESS
    )
    added_comment = _add_comment(case, user, comment, comment_type, is_internal=is_internal)
    added_files = add_attachments(case, user, files, kind=Attachment.Kind.COMPLETION)

    if new_status == Status.SOLVED:
        case.resolution_note = resolution_note.strip()
        _add_comment(case, user, case.resolution_note, Comment.Type.RESOLUTION)

    status_changed = _set_status(case, new_status, user)
    if not (status_changed or added_comment or added_files):
        raise WorkflowError(gettext("Nothing to save. Add a comment, a file or a new status."))
    case.save()

    if status_changed:
        if new_status == Status.SOLVED:
            # Acceptance criterion 18: the informed user receives a message.
            _notify_reporter(case, user, Status.SOLVED, message(gettext_noop("Resolution: %(value_0)s"), value_0=case.resolution_note))
            notify(
                admin_users(),
                case,
                Notification.Type.SOLVED,
                message(gettext_noop("%(value_0)s marked the case solved. Confirm and close it: %(value_1)s"), value_0=case.assigned_authority or 'Authority', value_1=case.title),
                actor=user,
            )
        else:
            _notify_reporter(case, user, new_status)
    elif added_comment and not is_internal:
        notify(
            [case.submitted_by],
            case,
            Notification.Type.STATUS_UPDATE,
            message(gettext_noop("New progress update on your case: %(value_0)s"), value_0=case.title),
            actor=user,
        )
    return case


@transaction.atomic
def admin_mark_solved(case, user, resolution_note):
    case = _lock(case)
    if case.status not in SOLVABLE_STATUSES:
        raise WorkflowError(gettext("A %(value_0)s case cannot be marked solved.") % {'value_0': case.get_status_display().lower()})
    if not (resolution_note or "").strip():
        raise WorkflowError(gettext("Add a resolution note before marking the case as solved."))
    case.resolution_note = resolution_note.strip()
    _add_comment(case, user, case.resolution_note, Comment.Type.RESOLUTION)
    _set_status(case, Status.SOLVED, user, "Marked solved by the administrator")
    case.save()
    _notify_reporter(case, user, Status.SOLVED, message(gettext_noop("Resolution: %(value_0)s"), value_0=case.resolution_note))
    return case


# ---------------------------------------------------------------------------
# Pending case reminders (Section 11, run daily by the scheduler)
# ---------------------------------------------------------------------------
def send_pending_reminders(now=None):
    """Remind the responsible people about cases with no action for too long.

    Unreviewed cases go to the administrators; not-started assigned cases go to
    the assigned authority. Each case is reminded at most once a day.
    """
    now = now or timezone.now()
    sent = 0
    candidates = (
        Case.objects.exclude(status__in=FINAL_STATUSES)
        .filter(status__in=[Status.SUBMITTED, Status.UNDER_REVIEW, Status.NOT_STARTED,
                            Status.ASSIGNED, Status.REOPENED])
        .select_related("assigned_authority")
    )
    for case in candidates:
        limit = (
            settings.REMINDER_AFTER_DAYS_URGENT
            if case.priority == Case.Priority.URGENT
            else settings.REMINDER_AFTER_DAYS_NORMAL
        )
        if case.age_days < limit:
            continue
        if case.last_reminder_at and now - case.last_reminder_at < timedelta(hours=20):
            continue
        if case.status in {Status.ASSIGNED, Status.REOPENED} and case.assigned_authority:
            recipients = authority_officers(case.assigned_authority)
            extra = [case.assigned_authority.email]
            who = message(gettext_noop("for %(authority)s"), authority=case.assigned_authority)
        else:
            recipients = admin_users()
            extra = []
            who = message(gettext_noop("waiting for the administrator"))
        with transaction.atomic():
            notify(
                recipients,
                case,
                Notification.Type.REMINDER,
                message(gettext_noop("Reminder: case %(value_0)s has had no action for %(value_1)s days (%(value_2)s): %(value_3)s"), value_0=who, value_1=case.age_days, value_2=Case.Priority(case.priority).label, value_3=case.title),
                extra_emails=extra,
            )
            Case.objects.filter(pk=case.pk).update(last_reminder_at=now)
        sent += 1
    return sent
