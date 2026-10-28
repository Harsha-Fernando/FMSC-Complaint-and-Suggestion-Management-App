"""Django admin for the system administrator (Section 6): records, settings, backups."""

from django.contrib import admin

from .models import Attachment, AuditLog, Authority, Case, Category, Comment, Notification


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    search_fields = ("name",)


@admin.register(Authority)
class AuthorityAdmin(admin.ModelAdmin):
    list_display = ("name", "officer_name", "designation", "email", "phone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "officer_name", "email")


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    readonly_fields = ("original_name", "file_type", "kind", "size", "uploaded_by", "uploaded_at")
    fields = readonly_fields
    can_delete = False


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    readonly_fields = ("comment_type", "text", "is_internal", "added_by", "added_at")
    fields = readonly_fields
    can_delete = False


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    """Read-only here: case changes must go through the app so they are audited."""

    list_display = ("case_number", "title", "case_type", "priority", "status", "assigned_authority",
                    "submitted_at")
    list_filter = ("status", "priority", "case_type", "category", "assigned_authority")
    search_fields = ("case_number", "title", "description")
    date_hierarchy = "submitted_at"
    inlines = [AttachmentInline, CommentInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "case", "action", "description", "user")
    list_filter = ("action",)
    search_fields = ("case__case_number", "description", "user__email")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("sent_at", "recipient", "notification_type", "case", "is_read", "emailed")
    list_filter = ("notification_type", "is_read", "emailed")
    search_fields = ("recipient__email", "case__case_number", "message")
