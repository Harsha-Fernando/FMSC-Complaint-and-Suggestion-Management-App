"""Legacy cleanup is explicit, recoverable, and never removes real submissions."""
import io
import json
import tempfile
from datetime import timedelta
from zipfile import ZipFile
from django.core.management import call_command
from django.utils import timezone
from accounts.models import User
from cases.models import AuditLog, Case, CaseCounter, Notification
from .helpers import CaseTestCase, PASSWORD


class DemoCleanupTests(CaseTestCase):
    def make_legacy_case(self):
        user = User.objects.create_user(username='legacy', email='student@fmsc.demo', password=PASSWORD)
        when = timezone.now() - timedelta(days=6)
        case = Case.objects.create(
            title='Broken chair in lecture hall', description='The third chair in row 4 has a broken leg and someone nearly fell.',
            location='Hall C, row 4', case_type='complaint', category=self.category,
            submitted_by=user, submitted_at=when,
        )
        AuditLog.objects.create(case=case, user=user, action='created', created_at=when)
        Notification.objects.create(case=case, recipient=self.admin, notification_type='new_case', message='Legacy sample')
        return case

    def test_preview_does_not_change_data(self):
        sample = self.make_legacy_case()
        output = io.StringIO()
        call_command('remove_demo_data', stdout=output)
        self.assertIn('Preview only', output.getvalue())
        self.assertTrue(Case.objects.filter(pk=sample.pk).exists())

    def test_apply_archives_only_identified_samples_and_preserves_accounts_and_counter(self):
        sample = self.make_legacy_case()
        real = self.submit(title='Actual chair complaint')
        user_ids = set(User.objects.values_list('pk', flat=True))
        counter = CaseCounter.objects.get().last_number
        with tempfile.TemporaryDirectory() as folder:
            call_command('remove_demo_data', apply=True, backup_dir=folder, stdout=io.StringIO())
            from pathlib import Path
            with ZipFile(next(Path(folder).glob('*.zip'))) as archive:
                records = json.loads(archive.read('records.json'))
                self.assertTrue(any(x['model']=='cases.case' and x['pk']==sample.pk for x in records))
        self.assertFalse(Case.objects.filter(pk=sample.pk).exists())
        self.assertTrue(Case.objects.filter(pk=real.pk).exists())
        self.assertFalse(Notification.objects.filter(message='Legacy sample').exists())
        self.assertEqual(set(User.objects.values_list('pk', flat=True)), user_ids)
        self.assertEqual(CaseCounter.objects.get().last_number, counter)

    def test_similar_real_submission_is_not_identified_as_sample(self):
        sample = self.make_legacy_case()
        real = self.submit(user=sample.submitted_by, title=sample.title,
                           description=sample.description, location=sample.location)
        with tempfile.TemporaryDirectory() as folder:
            call_command('remove_demo_data', apply=True, backup_dir=folder, stdout=io.StringIO())
        self.assertTrue(Case.objects.filter(pk=real.pk).exists())
