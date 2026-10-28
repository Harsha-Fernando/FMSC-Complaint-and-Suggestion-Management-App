from django.utils.translation import gettext_lazy as gettext
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator


class User(AbstractUser):
    """A faculty user. The role decides which screens and actions they get.

    Appendix A fields: user ID, name, email, role, user type, department/unit,
    contact number, active status. "User type" and "role" are the same thing
    here: one role per person keeps permissions easy to reason about.
    """

    class Role(models.TextChoices):
        STUDENT = "student", gettext("Student")
        LECTURER = "lecturer", gettext("Lecturer")
        ADMIN = "admin", gettext("Administrator")
        AUTHORITY = "authority", gettext("Relevant authority")
        MANAGEMENT = "management", gettext("Faculty management")
        SYSADMIN = "sysadmin", gettext("System administrator")

    email = models.EmailField("university email", unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    registration_number = models.CharField(
        max_length=40,
        unique=True,
        null=True,
        blank=True,
        help_text=gettext("Students sign in with this or their email."),
    )
    cpm_number = models.CharField(
        gettext("CPM number"), max_length=5, unique=True, null=True, blank=True,
        validators=[RegexValidator(r"\A[0-9]{5}\Z", gettext("Enter exactly five digits, for example 25678."))],
        help_text=gettext("Required for students. Keep leading zeros."),
    )
    lecturer_id = models.CharField(
        gettext("Lecturer ID"), max_length=40, unique=True, null=True, blank=True,
        validators=[RegexValidator(r"\A[A-Za-z0-9][A-Za-z0-9._/-]*\Z", gettext("Use letters, numbers, dots, hyphens, underscores or slashes."))],
        help_text=gettext("Required for lecturers. IDs are not case-sensitive."),
    )
    needs_password_setup = models.BooleanField(default=False, editable=False)
    department = models.CharField("department / unit", max_length=120, blank=True)
    contact_number = models.CharField(max_length=20, blank=True)
    authority = models.ForeignKey(
        "cases.Authority",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="officers",
        help_text=gettext("Only for relevant authority users: the unit whose cases they handle."),
    )

    class Meta:
        ordering = ["first_name", "last_name", "email"]
        constraints = [models.UniqueConstraint(Lower("lecturer_id"), name="unique_lecturer_id_casefold")]

    def __str__(self):
        return self.display_name

    def clean(self):
        super().clean()
        errors = {}
        if self.role == self.Role.STUDENT and not self.cpm_number:
            errors["cpm_number"] = gettext("A CPM number is required for a student.")
        if self.role == self.Role.LECTURER and not self.lecturer_id:
            errors["lecturer_id"] = gettext("A lecturer ID is required for a lecturer.")
        if self.cpm_number and self.role != self.Role.STUDENT:
            errors["cpm_number"] = gettext("Only students can have a CPM number.")
        if self.lecturer_id and self.role != self.Role.LECTURER:
            errors["lecturer_id"] = gettext("Only lecturers can have a lecturer ID.")
        if errors:
            raise ValidationError(errors)

    def set_password(self, raw_password):
        super().set_password(raw_password)
        self.needs_password_setup = False

    def set_unusable_password(self):
        super().set_unusable_password()
        self.needs_password_setup = False

    def save(self, *args, **kwargs):
        self.cpm_number = (self.cpm_number or "").strip() or None
        self.lecturer_id = (self.lecturer_id or "").strip().upper() or None
        if self.registration_number == "":
            self.registration_number = None
        if self.email:
            self.email = self.email.strip().lower()
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        return self.get_full_name() or self.email

    # Role helpers used by views and templates -------------------------------
    @property
    def is_reporter(self):
        return self.role in {self.Role.STUDENT, self.Role.LECTURER}

    @property
    def is_case_admin(self):
        return self.role in {self.Role.ADMIN, self.Role.SYSADMIN}

    @property
    def is_authority_officer(self):
        return self.role == self.Role.AUTHORITY

    @property
    def is_management_viewer(self):
        return self.role == self.Role.MANAGEMENT

    @property
    def can_view_all_cases(self):
        return self.is_case_admin or self.is_management_viewer

    @property
    def can_view_dashboards(self):
        return self.is_case_admin or self.is_management_viewer
