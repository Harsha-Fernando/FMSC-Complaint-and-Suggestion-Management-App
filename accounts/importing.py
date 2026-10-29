"""Shared, atomic roster import. Preview does not write users or generate passwords."""
import csv
import hashlib
import io
import json
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _
from accounts.models import User
from cases.models import Authority

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10000
COLUMNS = ('email', 'first_name', 'last_name', 'role', 'cpm_number', 'lecturer_id',
           'registration_number', 'department', 'contact_number', 'authority')
EDIT_FIELDS = ('first_name', 'last_name', 'role', 'cpm_number', 'lecturer_id',
               'registration_number', 'department', 'contact_number', 'authority_id')
SNAPSHOT_FIELDS = ('pk', 'email', 'username', *EDIT_FIELDS, 'is_active', 'is_staff', 'is_superuser')


def read_csv(file):
    data = file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValidationError(_('The CSV file must be no larger than 5 MB.'))
    try:
        source = data.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValidationError(_('Save the file as UTF-8 CSV and upload it again.')) from exc
    try:
        reader = csv.DictReader(io.StringIO(source, newline=''), strict=True)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)) or not {'email', 'role'}.issubset(headers) or set(headers) - set(COLUMNS):
            raise ValidationError(_('Use the template headers. Email and role columns are required; duplicate or unknown columns are not allowed.'))
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValidationError(_('Every CSV row must have the same number of columns as the header.'))
            if not any(value.strip() for value in row.values()):
                continue
            rows.append(row)
            if len(rows) > MAX_ROWS:
                raise ValidationError(_('Import no more than 10,000 accounts at a time.'))
        if not rows:
            raise ValidationError(_('The CSV file has no account rows.'))
        return rows
    except csv.Error as exc:
        raise ValidationError(_('The CSV file could not be read. Check its quoting and columns.')) from exc


def preview_import(rows, allowed_roles=None, lock=False):
    allowed_roles = set(allowed_roles or User.Role.values)
    users = User.objects.all()
    if lock:
        users = users.select_for_update()
    users = list(users)
    authorities = {a.name.casefold(): a for a in Authority.objects.all()}
    by_email = {u.email.casefold(): u for u in users}
    unique = {field: {} for field in ('username', 'registration_number', 'cpm_number', 'lecturer_id')}
    for user in users:
        for field, index in unique.items():
            value = getattr(user, field)
            if value:
                index[value.casefold()] = user.pk
    seen = {field: set() for field in ('email', *unique)}
    result = {'rows': [], 'problems': [], 'created': 0, 'updated': 0, 'objects': [], 'snapshots': []}
    if not rows or len(rows) > MAX_ROWS:
        result['problems'].append({'line': '-', 'errors': [_('Import between 1 and 10,000 accounts.')]})
    for number, source in enumerate(rows, start=2):
        raw = {key: str(value or '').strip() for key, value in source.items()}
        email = raw.get('email', '').lower()
        role = raw.get('role', '').lower()
        errors = []
        if role not in allowed_roles:
            errors.append(_('This import does not allow the selected role.'))
        original = by_email.get(email)
        if original and original.role != role:
            errors.append(_('An existing account has a different role. Change roles individually in user management.'))
        snapshot = {field: getattr(original, field) for field in SNAPSHOT_FIELDS} if original else None
        user = User(**{field.attname: getattr(original, field.attname) for field in User._meta.concrete_fields}) if original else User(email=email, username=email)
        user.email = email
        user.role = role
        if not original:
            user.set_unusable_password()
            user.needs_password_setup = True
            user.is_staff = role == User.Role.SYSADMIN
            user.is_superuser = role == User.Role.SYSADMIN
        for field in EDIT_FIELDS:
            if field in {'role', 'authority_id'}:
                continue
            if field in raw:
                value = raw[field]
                if field in {'cpm_number', 'lecturer_id', 'registration_number'}:
                    value = value or None
                if field == 'lecturer_id' and value:
                    value = value.upper()
                setattr(user, field, value)
        if role == User.Role.AUTHORITY:
            user.authority = authorities.get(raw.get('authority', '').casefold())
            if not user.authority:
                errors.append(_('Select an existing authority for this account.'))
        elif raw.get('authority'):
            errors.append(_('Only authority accounts can have an authority.'))
        try:
            user.clean_fields()
            user.clean()
        except ValidationError as exc:
            errors.extend(exc.messages)
        for field in seen:
            value = getattr(user, field)
            if not value:
                continue
            key = value.casefold()
            if key in seen[field]:
                errors.append(_('Duplicate value in the CSV column: %(column)s.') % {'column': field})
            seen[field].add(key)
            if field != 'email':
                owner = unique[field].get(key)
                if owner is not None and owner != user.pk:
                    errors.append(_('This value already belongs to another account: %(column)s.') % {'column': field})
        if errors:
            result['problems'].append({'line': number, 'errors': errors})
        action = _('Update') if original else _('Create')
        result['rows'].append({'line': number, 'email': email, 'name': user.get_full_name(), 'role': user.get_role_display(),
                               'cpm_number': user.cpm_number or '', 'lecturer_id': user.lecturer_id or '',
                               'registration_number': user.registration_number or '', 'department': user.department,
                               'contact_number': user.contact_number, 'action': action})
        result['objects'].append(user)
        result['snapshots'].append(snapshot)
        result['updated' if original else 'created'] += 1
    result['signature'] = hashlib.sha256(json.dumps(result['snapshots'], sort_keys=True).encode()).hexdigest()
    return result


def apply_import(rows, signature, allowed_roles=None):
    """Revalidate and lock current accounts, then commit the complete batch or none."""
    with transaction.atomic():
        plan = preview_import(rows, allowed_roles=allowed_roles, lock=True)
        if plan['problems']:
            return plan
        if plan['signature'] != signature:
            plan['problems'].append({'line': '-', 'errors': [_('Accounts changed after the preview. Upload the CSV again to review the latest changes.')]})
            return plan
        new = [user for user in plan['objects'] if user.pk is None]
        changed = [user for user in plan['objects'] if user.pk is not None]
        User.objects.bulk_create(new, batch_size=500)
        User.objects.bulk_update(changed, EDIT_FIELDS, batch_size=500)
        return plan
