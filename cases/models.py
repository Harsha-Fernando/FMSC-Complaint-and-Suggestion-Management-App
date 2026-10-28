"""Data model for the case workflow (Appendix A and Section 8 of the proposal)."""

from django.utils.translation import gettext_lazy as gettext
import uuid
from pathlib import Path

from django.conf import settings
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone


# ---------------------------------------------------------------------------
# Configurable lists (Section 12: changeable without code changes)
# ---------------------------------------------------------------------------
class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Authority(models.Model):
    """A unit that cases can be assigned to (Appendix A: Authority)."""

    name = models.CharField("authority name", max_length=120, unique=True)
    officer_name = models.CharField(max_length=120, blank=True)
    designation = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True, help_text=gettext("Assignment emails also go to this address."))
    phone = models.CharField(max_length=20, blank=True)
    unit = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(
        default=True, help_text=gettext("Inactive authorities stay on old cases but cannot receive new ones.")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "authorities"

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Case
# ---------------------------------------------------------------------------
class Status(models.TextChoices):
    """The ten statuses from Section 8, in lifecycle order."""

    SUBMITTED = "submitted", gettext("Submitted")
    UNDER_REVIEW = "under_review", gettext("Under review")
    NOT_STARTED = "not_started", gettext("Not started")
    ASSIGNED = "assigned", gettext("Assigned")
    IN_PROGRESS = "in_progress", gettext("In progress")
    WAITING_INFO = "waiting_info", gettext("Waiting for information")
    SOLVED = "solved", gettext("Solved")
    CLOSED = "closed", gettext("Closed")
    REJECTED = "rejected", gettext("Rejected")
    REOPENED = "reopened", gettext("Reopened")


# Status groups used by the dashboard definitions in Section 9.
FINAL_STATUSES = {Status.CLOSED, Status.REJECTED}
NOT_STARTED_STATUSES = {Status.NOT_STARTED, Status.ASSIGNED, Status.REOPENED}
WORKING_STATUSES = {Status.IN_PROGRESS, Status.WAITING_INFO}
RESOLVED_STATUSES = {Status.SOLVED, Status.CLOSED}
ASSIGNABLE_STATUSES = {
    Status.SUBMITTED,
    Status.UNDER_REVIEW,
    Status.NOT_STARTED,
    Status.ASSIGNED,
    Status.IN_PROGRESS,
    Status.WAITING_INFO,
    Status.REOPENED,
}
REJECTABLE_STATUSES = {Status.SUBMITTED, Status.UNDER_REVIEW, Status.NOT_STARTED, Status.ASSIGNED}
SOLVABLE_STATUSES = {Status.ASSIGNED, Status.IN_PROGRESS, Status.WAITING_INFO, Status.REOPENED}


class CaseQuerySet(models.QuerySet):
    def attempted(self):
        """Reviewed, assigned, started, solved, closed (or rejected after review)."""
        return self.exclude(status=Status.SUBMITTED)

    def not_attempted(self):
        """Submitted but nobody has reviewed or acted on it yet."""
        return self.filter(status=Status.SUBMITTED)

    def open(self):
        """Not yet closed. Rejected cases are finished too, so they are excluded."""
        return self.exclude(status__in=FINAL_STATUSES)

    def not_started(self):
        """Accepted or assigned, but the authority has not started action."""
        return self.filter(status__in=NOT_STARTED_STATUSES)

    def visible_to(self, user):
        if not user.is_authenticated:
            return self.none()
        if user.can_view_all_cases:
            return self
        if user.is_authority_officer:
            if user.authority_id is None:
                return self.none()
            return self.filter(assigned_authority_id=user.authority_id)
        return self.filter(submitted_by=user)


class CaseCounter(models.Model):
    """Keeps case numbers unique and sequential per year (FMSC-2026-001)."""

    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.year}: {self.last_number}"


class Case(models.Model):
    class CaseType(models.TextChoices):
        COMPLAINT = "complaint", gettext("Complaint")
        SUGGESTION = "suggestion", gettext("Suggestion")

    class Priority(models.TextChoices):
        URGENT = "urgent", gettext("Urgent")
        NORMAL = "normal", gettext("Normal")

    class RejectionReason(models.TextChoices):
        INVALID = "invalid", gettext("Invalid or not enough detail")
        DUPLICATE = "duplicate", gettext("Duplicate of another case")
        INAPPROPRIATE = "inappropriate", gettext("Inappropriate content")
        OUT_OF_SCOPE = "out_of_scope", gettext("Outside the faculty's scope")

    case_number = models.CharField(max_length=24, unique=True, editable=False)
    title = models.CharField(max_length=150)
    description = models.TextField()
    case_type = models.CharField(max_length=12, choices=CaseType.choices)
    priority = models.CharField(max_length=8, choices=Priority.choices, default=Priority.NORMAL)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="cases")
    location = models.CharField(max_length=150)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="submitted_cases"
    )
    assigned_authority = models.ForeignKey(
        Authority, null=True, blank=True, on_delete=models.PROTECT, related_name="cases"
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.SUBMITTED, db_index=True
    )
    declaration_accepted = models.BooleanField(default=False)

    internal_note = models.TextField(
        "admin note for authority", blank=True, help_text=gettext("Not shown to the person who reported.")
    )
    resolution_note = models.TextField(blank=True)
    rejection_reason = models.CharField(max_length=16, choices=RejectionReason.choices, blank=True)

    submitted_at = models.DateTimeField(default=timezone.now, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    solved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_reminder_at = models.DateTimeField(null=True, blank=True)

    objects = CaseQuerySet.as_manager()

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["assigned_authority", "status"]),
        ]

    def __str__(self):
        return f"{self.case_number}: {self.title}"

    def save(self, *args, **kwargs):
        if not self.case_number:
            self.case_number = self._next_case_number()
        super().save(*args, **kwargs)

    def _next_case_number(self):
        year = timezone.localtime(self.submitted_at or timezone.now()).year
        with transaction.atomic():
            counter, _ = CaseCounter.objects.select_for_update().get_or_create(year=year)
            counter.last_number += 1
            counter.save(update_fields=["last_number"])
            return f"FMSC-{year}-{counter.last_number:03d}"

    def get_absolute_url(self):
        return reverse("cases:detail", args=[self.case_number])

    # Derived values ---------------------------------------------------------
    @property
    def is_open(self):
        return self.status not in FINAL_STATUSES

    @property
    def is_not_started(self):
        return self.status in NOT_STARTED_STATUSES

    @property
    def age_days(self):
        """Days from submission to today (Section 9: age in days)."""
        end = timezone.localdate()
        if not self.is_open:
            finished = self.closed_at
            if self.status == Status.REJECTED:
                finished = self.reviewed_at
            end = timezone.localtime(finished or self.updated_at).date()
        return (end - timezone.localtime(self.submitted_at).date()).days

    @property
    def resolution_days(self):
        done = self.solved_at or self.closed_at
        if not done:
            return None
        return (done - self.submitted_at).total_seconds() / 86400


# ---------------------------------------------------------------------------
# Attachments, comments, notifications, audit trail
# ---------------------------------------------------------------------------
def attachment_upload_to(instance, filename):
    ext = Path(filename).suffix.lower()
    return f"case_files/{instance.case.case_number}/{uuid.uuid4().hex}{ext}"


class Attachment(models.Model):
    class FileType(models.TextChoices):
        IMAGE = "image", gettext("Image")
        VIDEO = "video", gettext("Video")

    class Kind(models.TextChoices):
        EVIDENCE = "evidence", gettext("Supporting evidence")
        COMPLETION = "completion", gettext("Completion evidence")
        REPLY = "reply", gettext("Added with a reply")

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=attachment_upload_to, max_length=255)
    original_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=8, choices=FileType.choices)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.EVIDENCE)
    size = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="attachments"
    )
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return self.original_name

    def get_absolute_url(self):
        return reverse("cases:attachment", args=[self.pk])


class Comment(models.Model):
    """Progress updates and notes (Appendix A: Comment / Progress Update)."""

    class Type(models.TextChoices):
        PROGRESS = "progress", gettext("Progress update")
        INFO_REQUEST = "info_request", gettext("Information requested")
        USER_REPLY = "user_reply", gettext("Reply from reporter")
        ADMIN_NOTE = "admin_note", gettext("Admin note")
        RESOLUTION = "resolution", gettext("Resolution note")
        REJECTION = "rejection", gettext("Rejection reason")
        FEEDBACK = "feedback", gettext("Reporter feedback")
        REOPEN = "reopen", gettext("Reopen reason")

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="comments")
    text = models.TextField()
    comment_type = models.CharField(max_length=16, choices=Type.choices, default=Type.PROGRESS)
    is_internal = models.BooleanField(
        default=False, help_text=gettext("Internal comments are hidden from the person who reported.")
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="case_comments"
    )
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["added_at"]

    def __str__(self):
        return f"{self.get_comment_type_display()} on {self.case.case_number}"


class Notification(models.Model):
    class Type(models.TextChoices):
        NEW_CASE = "new_case", gettext("New case")
        ASSIGNED = "assigned", gettext("Case assigned")
        STATUS_UPDATE = "status_update", gettext("Status update")
        INFO_REQUEST = "info_request", gettext("Information requested")
        SOLVED = "solved", gettext("Case solved")
        REPLY = "reply", gettext("Reply received")
        FEEDBACK = "feedback", gettext("Reporter feedback")
        REMINDER = "reminder", gettext("Pending case reminder")

    case = models.ForeignKey(
        Case, null=True, blank=True, on_delete=models.CASCADE, related_name="notifications"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(max_length=16, choices=Type.choices)
    message = models.CharField(max_length=400)
    message_template = models.TextField(blank=True)
    message_parameters = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)
    emailed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-sent_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    @property
    def localized_message(self):
        from .messages import render_message
        return render_message(self.message_template, self.message_parameters) if self.message_template else gettext(self.message)

    def __str__(self):
        return f"To {self.recipient}: {self.message[:40]}"


class AuditLog(models.Model):
    """Full history of who changed what (Section 11: audit trail)."""

    class Action(models.TextChoices):
        CREATED = "created", gettext("Case submitted")
        STATUS_CHANGED = "status_changed", gettext("Status changed")
        ASSIGNED = "assigned", gettext("Authority assigned")
        FIELD_CHANGED = "field_changed", gettext("Field changed")
        COMMENT_ADDED = "comment_added", gettext("Comment added")
        ATTACHMENT_ADDED = "attachment_added", gettext("Attachment added")
        CONFIG_CHANGED = "config_changed", gettext("Configuration changed")

    case = models.ForeignKey(
        Case, null=True, blank=True, on_delete=models.PROTECT, related_name="audit_logs"
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    field = models.CharField(max_length=60, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.get_action_display()} ({self.created_at:%Y-%m-%d %H:%M})"
