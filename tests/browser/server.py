"""Ephemeral browser-test environment. Never connects to the working database."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DJANGO_DEBUG'] = 'true'

from django.conf import settings
with tempfile.TemporaryDirectory(prefix='fmsc-ui-tests-') as temp:
    settings.DATABASES = {'default': {'ENGINE':'django.db.backends.sqlite3', 'NAME':str(Path(temp)/'test.sqlite3')}}
    settings.MEDIA_ROOT = str(Path(temp)/'media')
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    settings.NOTIFY_BY_EMAIL = False
    settings.ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']
    import django
    django.setup()
    from django.core.management import call_command
    from accounts.models import User
    from cases.models import Authority, Category
    call_command('migrate', verbosity=0)
    unit = Authority.objects.create(name='Facilities Unit')
    Category.objects.create(name='Facilities')
    Category.objects.create(name='IT services')
    for role in User.Role.values:
        User.objects.create_user(username=f'{role}@test.example',email=f'{role}@test.example',
            password='Browser-Test-2026!', first_name=role.title(), role=role,
            authority=unit if role=='authority' else None,
            is_staff=role=='sysadmin', is_superuser=role=='sysadmin')
    call_command('runserver', '127.0.0.1:8765', use_reloader=False, verbosity=0)
