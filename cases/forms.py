from django.utils.translation import gettext_lazy as gettext
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from django.db.models import Q

from .models import ASSIGNABLE_STATUSES, Attachment, Authority, Case, Category, Status
from .services import ADMIN_REVIEW_STATUSES, ADMIN_REVIEWABLE_FROM, AUTHORITY_TRANSITIONS
from .validators import validate_upload


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """A file field that accepts several files and returns a list."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        kwargs.setdefault("required", False)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        return [super(MultipleFileField, self).clean(item, initial) for item in data if item]


def _accept(extensions):
    return ",".join(f".{ext}" for ext in extensions)


class EvidenceUploadMixin:
    """Adds image and video upload fields and validates them together."""

    image_field = "images"
    video_field = "videos"

    def add_upload_fields(self, image_label="Images", video_label="Videos"):
        self.fields[self.image_field] = MultipleFileField(
            label=image_label,
            widget=MultipleFileInput(
                attrs={
                    "accept": _accept(settings.ALLOWED_IMAGE_EXTENSIONS),
                    "data-max-mb": settings.MAX_IMAGE_SIZE_MB,
                    "data-kind": "image",
                }
            ),
            help_text=(
                gettext("%(value_0)s, up to %(value_1)s MB each.") % {'value_0': ', '.join((e.upper() for e in settings.ALLOWED_IMAGE_EXTENSIONS)), 'value_1': settings.MAX_IMAGE_SIZE_MB}
            ),
        )
        self.fields[self.video_field] = MultipleFileField(
            label=video_label,
            widget=MultipleFileInput(
                attrs={
                    "accept": _accept(settings.ALLOWED_VIDEO_EXTENSIONS),
                    "data-max-mb": settings.MAX_VIDEO_SIZE_MB,
                    "data-kind": "video",
                }
            ),
            help_text=(
                gettext("%(value_0)s, up to %(value_1)s MB each. Keep clips short.") % {'value_0': ', '.join((e.upper() for e in settings.ALLOWED_VIDEO_EXTENSIONS)), 'value_1': settings.MAX_VIDEO_SIZE_MB}
            ),
        )

    def clean_uploads(self):
        files = []
        errors = []
        for field_name, file_type in (
            (self.image_field, Attachment.FileType.IMAGE),
            (self.video_field, Attachment.FileType.VIDEO),
        ):
            for uploaded in self.cleaned_data.get(field_name) or []:
                try:
                    detected, content_type = validate_upload(uploaded, file_type)
                    files.append((uploaded, detected, content_type))
                except ValidationError as exc:
                    errors.extend(exc.messages)
        if len(files) + len(errors) > settings.MAX_ATTACHMENTS_PER_UPLOAD:
            errors.append(
                gettext("Attach at most %(count)s files at a time.") % {"count": settings.MAX_ATTACHMENTS_PER_UPLOAD}
            )
        if errors:
            raise ValidationError(errors)
        return files


class CaseSubmissionForm(EvidenceUploadMixin, forms.ModelForm):
    """Wireframe 3: submit a complaint or suggestion."""

    declaration = forms.BooleanField(
        label=gettext("I confirm that the information submitted is accurate to the best of my knowledge."),
        required=True,
        error_messages={"required": gettext("Tick the declaration to submit the case.")},
    )

    class Meta:
        model = Case
        fields = ["case_type", "priority", "category", "location", "title", "description"]
        widgets = {
            "case_type": forms.RadioSelect,
            "priority": forms.RadioSelect,
            "title": forms.TextInput(attrs={"placeholder": gettext("e.g. Projector not working in Hall A")}),
            "location": forms.TextInput(attrs={"placeholder": gettext("Building, room or office")}),
            "description": forms.Textarea(
                attrs={"rows": 6, "placeholder": gettext("What happened, when, and who is affected?")}
            ),
        }
        labels = {"case_type": gettext("Case type"), "title": gettext("Short title"), "priority": gettext("Priority"), "category": gettext("Category"), "location": gettext("Location"), "description": gettext("Description")}
        help_texts = {
            "priority": gettext("Urgent means a safety risk or something stopping classes or exams today."),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        self.fields["category"].empty_label = gettext("Choose a category")
        self.fields["case_type"].choices = Case.CaseType.choices
        self.fields["priority"].choices = Case.Priority.choices
        self.fields["priority"].initial = Case.Priority.NORMAL
        self.add_upload_fields(image_label=gettext("Photos"), video_label=gettext("Videos"))

    def clean(self):
        cleaned = super().clean()
        try:
            cleaned["files"] = self.clean_uploads()
        except ValidationError as exc:
            self.add_error(None, exc)
        return cleaned


class ReplyForm(EvidenceUploadMixin, forms.Form):
    text = forms.CharField(
        label=gettext("Your reply"),
        widget=forms.Textarea(attrs={"rows": 4}),
        max_length=4000,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_upload_fields(image_label=gettext("Add photos"), video_label=gettext("Add videos"))

    def clean(self):
        cleaned = super().clean()
        try:
            cleaned["files"] = self.clean_uploads()
        except ValidationError as exc:
            self.add_error(None, exc)
        return cleaned


class FeedbackForm(forms.Form):
    text = forms.CharField(
        label=gettext("What is still not right?"),
        widget=forms.Textarea(attrs={"rows": 3}),
        max_length=2000,
    )


# ---------------------------------------------------------------------------
# Administrator forms (Wireframe 5)
# ---------------------------------------------------------------------------
class AdminReviewForm(forms.Form):
    """Wireframe 5 in one form: status, category, priority, assign to, internal note.

    "Save changes" stores the review; "Assign case" stores it and assigns in one step.
    """

    status = forms.ChoiceField(label=gettext("Status"))
    category = forms.ModelChoiceField(label=gettext("Category"), queryset=Category.objects.all(), required=True)
    priority = forms.ChoiceField(label=gettext("Priority"), choices=Case.Priority.choices)
    authority = forms.ModelChoiceField(
        label=gettext("Assign to"),
        queryset=Authority.objects.filter(is_active=True),
        required=False,
        empty_label=gettext("Choose an authority"),
    )
    internal_note = forms.CharField(
        label=gettext("Admin note for authority"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=gettext("The assigned authority sees this. The reporter does not."),
    )

    def __init__(self, *args, case, action="save", **kwargs):
        super().__init__(*args, **kwargs)
        self.case = case
        self.action = action
        if case.status in ADMIN_REVIEWABLE_FROM:
            choices = [(s, Status(s).label) for s in ADMIN_REVIEW_STATUSES]
            if case.status not in ADMIN_REVIEW_STATUSES:
                choices = [(case.status, gettext("%(status)s (no change)") % {"status": Status(case.status).label})] + choices
            self.fields["status"].choices = choices
            # Assigning sets the status to Assigned, so the dropdown is not needed then.
            self.fields["status"].required = action != "assign"
        else:
            del self.fields["status"]
        if case.status not in ASSIGNABLE_STATUSES:
            del self.fields["authority"]
        else:
            # Needed only when assigning, so don't label it "optional".
            self.fields["authority"].hide_optional = True
        self.fields["category"].queryset = Category.objects.filter(
            Q(is_active=True) | Q(pk=case.category_id)
        )
        if not self.is_bound:
            self.initial.update(
                {
                    "status": case.status,
                    "category": case.category_id,
                    "priority": case.priority,
                    "internal_note": case.internal_note,
                    "authority": case.assigned_authority_id
                    if case.assigned_authority and case.assigned_authority.is_active
                    else None,
                }
            )

    def clean_status(self):
        value = self.cleaned_data.get("status")
        return None if value == self.case.status else value

    def clean(self):
        cleaned = super().clean()
        if self.action == "assign":
            if "authority" not in self.fields:
                raise ValidationError(
                    gettext("A %(value_0)s case cannot be assigned.") % {'value_0': self.case.get_status_display().lower()}
                )
            if not cleaned.get("authority"):
                self.add_error("authority", gettext("Choose the authority to assign this case to."))
        return cleaned


class RejectForm(forms.Form):
    reason = forms.ChoiceField(label=gettext("Reason"), choices=Case.RejectionReason.choices)
    note = forms.CharField(
        label=gettext("Message to the reporter"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text=gettext("Optional. For a duplicate, give the original case number."),
    )


class CloseForm(forms.Form):
    note = forms.CharField(
        label=gettext("Closing note"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )


class ReopenForm(forms.Form):
    reason = forms.CharField(
        label=gettext("Why is the resolution not satisfactory?"),
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class AdminSolveForm(forms.Form):
    resolution_note = forms.CharField(
        label=gettext("Resolution note"),
        widget=forms.Textarea(attrs={"rows": 3}),
        error_messages={"required": gettext("Add a resolution note before marking the case as solved.")},
    )


# ---------------------------------------------------------------------------
# Authority form (Wireframe 7)
# ---------------------------------------------------------------------------
class ProgressUpdateForm(EvidenceUploadMixin, forms.Form):
    image_field = "completion_images"
    video_field = "completion_videos"

    new_status = forms.ChoiceField(label=gettext("New status"))
    comment = forms.CharField(
        label=gettext("Progress comment"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": gettext("Action taken or current progress")}),
        help_text=gettext("If you choose “Waiting for information”, write the question for the reporter here."),
    )
    is_internal = forms.BooleanField(
        label=gettext("Internal only (hide this comment from the reporter)"), required=False
    )
    resolution_note = forms.CharField(
        label=gettext("Resolution note"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=gettext("Required when marking the case as solved."),
    )

    def __init__(self, *args, case, **kwargs):
        super().__init__(*args, **kwargs)
        self.case = case
        self.fields["resolution_note"].hide_optional = True
        allowed = AUTHORITY_TRANSITIONS.get(case.status, [])
        statuses = [case.status] + [s for s in allowed if s != case.status]
        self.fields["new_status"].choices = [
            (s, gettext("%(status)s (no change)") % {"status": Status(s).label} if s == case.status else Status(s).label)
            for s in statuses
        ]
        self.fields["new_status"].initial = (
            Status.IN_PROGRESS if case.status in {Status.ASSIGNED, Status.REOPENED} else case.status
        )
        self.add_upload_fields(
            image_label=gettext("Completion photos"), video_label=gettext("Completion videos")
        )

    def clean(self):
        cleaned = super().clean()
        new_status = cleaned.get("new_status")
        if new_status == Status.SOLVED and not (cleaned.get("resolution_note") or "").strip():
            self.add_error("resolution_note", gettext("Add a resolution note before marking the case as solved."))
        if (
            new_status == Status.WAITING_INFO
            and self.case.status != Status.WAITING_INFO
            and not (cleaned.get("comment") or "").strip()
        ):
            self.add_error("comment", gettext("Write what information you need from the reporter."))
        try:
            cleaned["files"] = self.clean_uploads()
        except ValidationError as exc:
            self.add_error(None, exc)
        return cleaned


# ---------------------------------------------------------------------------
# Dashboard and report filters (Wireframe 4, acceptance criterion 22)
# ---------------------------------------------------------------------------
class CaseFilterForm(forms.Form):
    date_from = forms.DateField(
        label=gettext("From"), required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    date_to = forms.DateField(
        label=gettext("To"), required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    category = forms.ModelChoiceField(
        label=gettext("Category"), queryset=Category.objects.all(), required=False, empty_label=gettext("All categories")
    )
    authority = forms.ModelChoiceField(
        label=gettext("Authority"), queryset=Authority.objects.all(), required=False, empty_label=gettext("All authorities")
    )
    priority = forms.ChoiceField(
        label=gettext("Priority"), choices=[("", gettext("All priorities"))] + list(Case.Priority.choices), required=False
    )
    status = forms.ChoiceField(
        label=gettext("Status"), choices=[("", gettext("All statuses"))] + list(Status.choices), required=False
    )
    case_type = forms.ChoiceField(
        label=gettext("Type"), choices=[("", gettext("All types"))] + list(Case.CaseType.choices), required=False
    )
    q = forms.CharField(
        label=gettext("Search"),
        required=False,
        widget=forms.TextInput(attrs={"placeholder": gettext("Case number or title")}),
    )

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("date_from"), cleaned.get("date_to")
        if start and end and start > end:
            self.add_error("date_to", gettext("The end date is before the start date."))
        return cleaned

    def apply(self, queryset, include_status=True):
        if not self.is_valid():
            return queryset
        data = self.cleaned_data
        if data.get("date_from"):
            queryset = queryset.filter(submitted_at__date__gte=data["date_from"])
        if data.get("date_to"):
            queryset = queryset.filter(submitted_at__date__lte=data["date_to"])
        if data.get("category"):
            queryset = queryset.filter(category=data["category"])
        if data.get("authority"):
            queryset = queryset.filter(assigned_authority=data["authority"])
        if data.get("priority"):
            queryset = queryset.filter(priority=data["priority"])
        if data.get("case_type"):
            queryset = queryset.filter(case_type=data["case_type"])
        if include_status and data.get("status"):
            queryset = queryset.filter(status=data["status"])
        if data.get("q"):
            from django.db.models import Q

            term = data["q"].strip()
            queryset = queryset.filter(Q(case_number__icontains=term) | Q(title__icontains=term))
        return queryset

    @property
    def active_count(self):
        if not self.is_bound or not self.is_valid():
            return 0
        return sum(1 for value in self.cleaned_data.values() if value)


# ---------------------------------------------------------------------------
# Configuration forms (authority list, categories)
# ---------------------------------------------------------------------------
class AuthorityForm(forms.ModelForm):
    class Meta:
        model = Authority
        fields = ["name", "officer_name", "designation", "email", "phone", "unit", "is_active"]
        labels = {"is_active": gettext("Active (can receive new cases)"), "name": gettext("Name"), "officer_name": gettext("Contact officer"), "designation": gettext("Designation"), "email": gettext("Email"), "phone": gettext("Phone"), "unit": gettext("Unit")}


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description", "sort_order", "is_active"]
        labels = {"is_active": gettext("Active (shown on the submission form)"), "sort_order": gettext("Order in list"), "name": gettext("Name"), "description": gettext("Description")}
