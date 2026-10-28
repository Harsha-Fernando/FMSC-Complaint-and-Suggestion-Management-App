from django.urls import path

from . import configuration_views, dashboard_views, notification_views, views

app_name = "cases"

urlpatterns = [
    path("", views.home, name="home"),
    # Student / lecturer
    path("cases/new/", views.case_create, name="create"),
    path("cases/mine/", views.my_cases, name="my_cases"),
    # Every role reaches a case through the same address
    path("cases/<str:case_number>/", views.case_detail, name="detail"),
    path("cases/<str:case_number>/reply/", views.case_reply, name="reply"),
    path("cases/<str:case_number>/feedback/", views.case_feedback, name="feedback"),
    # Administrator actions
    path("cases/<str:case_number>/review/", views.admin_review, name="admin_review"),
    path("cases/<str:case_number>/reject/", views.admin_reject, name="admin_reject"),
    path("cases/<str:case_number>/close/", views.admin_close, name="admin_close"),
    path("cases/<str:case_number>/reopen/", views.admin_reopen, name="admin_reopen"),
    path("cases/<str:case_number>/solve/", views.admin_solve, name="admin_solve"),
    # Authority action
    path("cases/<str:case_number>/progress/", views.authority_update, name="authority_update"),
    # Files
    path("attachments/<int:pk>/", views.attachment_download, name="attachment"),
    # Dashboards and reports
    path("dashboard/", dashboard_views.admin_dashboard, name="admin_dashboard"),
    path("dashboard/management/", dashboard_views.management_dashboard, name="management_dashboard"),
    path("work-queue/", dashboard_views.authority_dashboard, name="authority_dashboard"),
    path("reports/", dashboard_views.reports, name="reports"),
    # Notifications
    path("notifications/summary/", notification_views.notification_summary, name="notification_summary"),
    path("notifications/", notification_views.notification_list, name="notifications"),
    path("notifications/<int:pk>/open/", notification_views.notification_open, name="notification_open"),
    path("notifications/read-all/", notification_views.notifications_mark_all_read, name="notifications_read_all"),
    # Configuration
    path("settings/authorities/", configuration_views.authority_list, name="authority_list"),
    path("settings/authorities/new/", configuration_views.authority_edit, name="authority_create"),
    path("settings/authorities/<int:pk>/", configuration_views.authority_edit, name="authority_edit"),
    path("settings/authorities/<int:pk>/toggle/", configuration_views.authority_toggle, name="authority_toggle"),
    path("settings/authorities/<int:pk>/delete/", configuration_views.authority_delete, name="authority_delete"),
    path("settings/categories/", configuration_views.category_list, name="category_list"),
    path("settings/categories/new/", configuration_views.category_edit, name="category_create"),
    path("settings/categories/<int:pk>/", configuration_views.category_edit, name="category_edit"),
    path("settings/categories/<int:pk>/toggle/", configuration_views.category_toggle, name="category_toggle"),
]
