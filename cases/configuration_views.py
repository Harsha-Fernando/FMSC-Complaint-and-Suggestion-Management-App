"""Authority list and categories (acceptance criterion 15, Section 12 maintainability)."""

from django.utils.translation import gettext_lazy as gettext
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import AuthorityForm, CategoryForm
from .models import AuditLog, Authority, Category, Status
from .permissions import CASE_ADMIN_ROLES, role_required
from .services import log_audit


def _describe_changes(form):
    parts = []
    for name in form.changed_data:
        parts.append(f"{form.fields[name].label or name}: {form.cleaned_data.get(name)}")
    return "; ".join(parts)


# Authorities ---------------------------------------------------------------
@role_required(*CASE_ADMIN_ROLES)
def authority_list(request):
    authorities = Authority.objects.annotate(
        open_cases=Count("cases", filter=~Q(cases__status__in=[Status.CLOSED, Status.REJECTED]), distinct=True),
        total_cases=Count("cases", distinct=True),
        officer_count=Count("officers", filter=Q(officers__is_active=True), distinct=True),
    )
    return render(request, "cases/settings/authority_list.html", {"authorities": authorities})


@role_required(*CASE_ADMIN_ROLES)
def authority_edit(request, pk=None):
    authority = get_object_or_404(Authority, pk=pk) if pk else None
    form = AuthorityForm(request.POST or None, instance=authority)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        log_audit(
            None, request.user, AuditLog.Action.CONFIG_CHANGED,
            f"Authority {gettext('updated') if authority else gettext('added')}: {saved.name}",
            field="authority", new=_describe_changes(form),
        )
        messages.success(request, gettext("%(value_0)s %(value_1)s.") % {'value_0': saved.name, 'value_1': gettext('updated') if authority else gettext('added')})
        return redirect("cases:authority_list")
    return render(request, "cases/settings/authority_form.html", {"form": form, "authority": authority})


@require_POST
@role_required(*CASE_ADMIN_ROLES)
def authority_toggle(request, pk):
    authority = get_object_or_404(Authority, pk=pk)
    authority.is_active = not authority.is_active
    authority.save(update_fields=["is_active", "updated_at"])
    state = gettext("activated") if authority.is_active else gettext("deactivated")
    log_audit(None, request.user, AuditLog.Action.CONFIG_CHANGED, f"Authority {state}: {authority.name}",
              field="authority.is_active", new=authority.is_active)
    messages.success(request, gettext("%(value_0)s %(value_1)s.") % {'value_0': authority.name, 'value_1': state})
    return redirect("cases:authority_list")


@require_POST
@role_required(*CASE_ADMIN_ROLES)
def authority_delete(request, pk):
    authority = get_object_or_404(Authority, pk=pk)
    if authority.cases.exists():
        messages.error(
            request,
            gettext("%(value_0)s has cases on record, so it cannot be deleted. Deactivate it instead: it keeps its history but gets no new cases.") % {'value_0': authority.name},
        )
        return redirect("cases:authority_list")
    name = authority.name
    authority.delete()
    log_audit(None, request.user, AuditLog.Action.CONFIG_CHANGED, f"Authority deleted: {name}",
              field="authority", old=name)
    messages.success(request, gettext("%(value_0)s deleted.") % {'value_0': name})
    return redirect("cases:authority_list")


# Categories ------------------------------------------------------------------
@role_required(*CASE_ADMIN_ROLES)
def category_list(request):
    categories = Category.objects.annotate(total_cases=Count("cases"))
    return render(request, "cases/settings/category_list.html", {"categories": categories})


@role_required(*CASE_ADMIN_ROLES)
def category_edit(request, pk=None):
    category = get_object_or_404(Category, pk=pk) if pk else None
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        log_audit(
            None, request.user, AuditLog.Action.CONFIG_CHANGED,
            f"Category {gettext('updated') if category else gettext('added')}: {saved.name}",
            field="category", new=_describe_changes(form),
        )
        messages.success(request, gettext("Category %(value_0)s %(value_1)s.") % {'value_0': saved.name, 'value_1': gettext('updated') if category else gettext('added')})
        return redirect("cases:category_list")
    return render(request, "cases/settings/category_form.html", {"form": form, "category": category})


@require_POST
@role_required(*CASE_ADMIN_ROLES)
def category_toggle(request, pk):
    category = get_object_or_404(Category, pk=pk)
    category.is_active = not category.is_active
    category.save(update_fields=["is_active"])
    state = gettext("shown on the form") if category.is_active else gettext("hidden from the form")
    log_audit(None, request.user, AuditLog.Action.CONFIG_CHANGED, f"Category {category.name} {state}",
              field="category.is_active", new=category.is_active)
    messages.success(request, gettext("%(value_0)s is now %(value_1)s.") % {'value_0': category.name, 'value_1': state})
    return redirect("cases:category_list")
