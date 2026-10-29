"""Language preferences and system-administrator account imports."""
import csv
import secrets

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST
from django.views.i18n import set_language

from .forms import AccountCSVForm
from .importing import COLUMNS, apply_import, preview_import, read_csv
from .models import User


@require_POST
def language_set(request):
    if request.POST.get("language") not in dict(settings.LANGUAGES):
        return HttpResponseBadRequest(gettext("Unsupported language."))
    return set_language(request)


REPORTER_ROLES = {User.Role.STUDENT, User.Role.LECTURER}


def require_account_manager(request):
    if not (request.user.is_active and request.user.is_staff and request.user.role == User.Role.SYSADMIN):
        raise PermissionDenied


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def account_import(request):
    require_account_manager(request)
    form = AccountCSVForm()
    plan = None
    token = None
    if request.method == 'POST' and request.POST.get('action') == 'confirm':
        pending = request.session.get('account_import')
        if not pending or pending['owner'] != request.user.pk or not secrets.compare_digest(str(request.POST.get('token', '')), pending['token']) or timezone.now().timestamp() - pending['created_at'] > 900:
            return HttpResponseBadRequest(gettext('This preview has expired or is invalid. Upload the CSV again.'))
        try:
            plan = apply_import(pending['rows'], pending['signature'], allowed_roles=REPORTER_ROLES)
        except IntegrityError:
            plan = {'problems': [{'line': '-', 'errors': [gettext('Accounts changed during import. No accounts were changed. Upload the CSV again.')]}], 'rows': [], 'created': 0, 'updated': 0}
        del request.session['account_import']
        if not plan['problems']:
            messages.success(request, gettext('Created: %(created)s · Updated: %(updated)s.') % {'created': plan['created'], 'updated': plan['updated']})
            return HttpResponseRedirect(reverse('admin:accounts_user_changelist'))
    elif request.method == 'POST':
        request.session.pop('account_import', None)
        form = AccountCSVForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                rows = read_csv(form.cleaned_data['csv_file'])
                plan = preview_import(rows, allowed_roles=REPORTER_ROLES)
                if not plan['problems']:
                    token = secrets.token_urlsafe(32)
                    request.session['account_import'] = {'owner': request.user.pk, 'token': token, 'created_at': timezone.now().timestamp(), 'rows': rows, 'signature': plan['signature']}
            except ValidationError as exc:
                form.add_error('csv_file', exc)
                plan = {'problems': [{'line': '-', 'errors': exc.messages}], 'rows': [], 'created': 0, 'updated': 0}
    context = {
        **admin.site.each_context(request), 'title': gettext('Import accounts'), 'form': form,
        'problems': plan['problems'][:100] if plan else [], 'token': token,
        'preview_rows': plan['rows'][:50] if plan else [], 'plan': plan,
        'opts': User._meta,
    }
    return render(request, 'admin/accounts/user/import.html', context)


@login_required
@never_cache
def account_import_template(request):
    require_account_manager(request)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="account-import-template.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow([column for column in COLUMNS if column != 'authority'])
    writer.writerow(['student@example.edu', 'Amaya', 'Perera', 'student', '25678', '', 'FMSC/2026/001', 'Accounting', ''])
    writer.writerow(['lecturer@example.edu', 'Saman', 'Kumara', 'lecturer', '', 'LEC-001', '', 'Accounting', ''])
    return response
