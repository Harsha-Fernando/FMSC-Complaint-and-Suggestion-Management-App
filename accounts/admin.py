from django.utils.translation import gettext_lazy as gettext
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User
from django.urls import path
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from .views import account_import, account_import_template


class DepartmentListFilter(admin.AllValuesFieldListFilter):
    def choices(self, changelist):
        for choice in super().choices(changelist):
            if choice["display"] == "":
                choice["display"] = gettext("Not specified")
            yield choice


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """System administrators manage users and roles here (Section 6)."""

    change_list_template = "admin/accounts/user/change_list.html"
    list_display = ("email", "full_name", "role", "department", "is_active")
    list_filter = ("is_active", ("department", DepartmentListFilter))
    search_fields = ("email", "first_name", "last_name", "registration_number", "cpm_number", "lecturer_id", "username")
    ordering = ("email",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (gettext("Person"), {"fields": ("first_name", "last_name", "email", "contact_number")}),
        (gettext("Faculty role"), {"fields": ("role", "cpm_number", "lecturer_id", "registration_number", "department", "authority")}),
        (gettext("Access"), {"fields": ("is_active", "is_staff", "is_superuser", "groups")}),
        (gettext("Dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "role",
                    "cpm_number",
                    "lecturer_id",
                    "registration_number",
                    "department",
                    "authority",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    @admin.display(description=gettext("Name"), ordering="first_name")
    def full_name(self, obj):
        return obj.get_full_name() or "—"

    def get_list_display(self, request):
        role = request.GET.get("role__exact")
        common = ("email", "full_name")
        if role == User.Role.STUDENT:
            return (*common, "cpm_number", "registration_number", "department", "is_active")
        if role == User.Role.LECTURER:
            return (*common, "lecturer_id", "department", "is_active")
        if role == User.Role.AUTHORITY:
            return (*common, "authority", "is_active")
        if role in User.Role.values:
            return (*common, "department", "is_active")
        return self.list_display

    def get_list_filter(self, request):
        if request.GET.get("role__exact") == User.Role.AUTHORITY:
            return ("is_active", "authority", ("department", DepartmentListFilter))
        return self.list_filter

    def changelist_view(self, request, extra_context=None):
        selected = request.GET.get("role__exact", "")
        if "role__exact" in request.GET and not selected:
            query = request.GET.copy()
            query.pop("role__exact")
            return HttpResponseRedirect(request.path + ("?" + query.urlencode() if query else ""))
        if selected and selected not in User.Role.values:
            return HttpResponseBadRequest(gettext("Select a valid role."))
        excluded = {"role__exact", "o", "p", "authority__id__exact", "authority__isnull"}
        preserved = [(key, value) for key in request.GET for value in request.GET.getlist(key) if key not in excluded]
        context = {
            **(extra_context or {}), "selected_role": selected,
            "account_roles": User.Role.choices, "role_filter_preserved": preserved,
        }
        return super().changelist_view(request, extra_context=context)

    def get_urls(self):
        return [
            path("import/", account_import, name="accounts_user_import"),
            path("import/template/", account_import_template, name="accounts_user_import_template"),
        ] + super().get_urls()

    def save_model(self, request, obj, form, change):
        if not obj.username:
            obj.username = obj.email
        # The application role and Django's administrative permissions must agree.
        obj.is_staff = obj.role == User.Role.SYSADMIN
        obj.is_superuser = obj.role == User.Role.SYSADMIN
        super().save_model(request, obj, form, change)
