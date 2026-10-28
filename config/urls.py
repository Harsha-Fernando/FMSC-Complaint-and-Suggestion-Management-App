from django.contrib import admin
from accounts.views import language_set
from django.utils.translation import gettext_lazy as gettext
from django.urls import include, path
from django.views.i18n import JavaScriptCatalog
from django.views.decorators.cache import never_cache

admin.site.site_header = gettext("FMSC Case Desk: system administration")
admin.site.site_title = gettext("FMSC Case Desk admin")
admin.site.index_title = gettext("Users, roles and records")

urlpatterns = [
    path("i18n/setlang/", language_set, name="set_language"),
    path("jsi18n/", never_cache(JavaScriptCatalog.as_view()), name="javascript-catalog"),
    path("system-admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("cases.urls")),
]
