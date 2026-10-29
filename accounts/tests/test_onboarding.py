"""Real account onboarding must work without publishing or emailing passwords."""
import io
import tempfile
from pathlib import Path
from django.core import mail
from django.core.management import call_command
from accounts.models import User
from cases.tests.helpers import CaseTestCase


class AccountOnboardingTests(CaseTestCase):
    def test_imported_user_can_request_password_setup_email(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'users.csv'
            path.write_text('email,first_name,last_name,role,cpm_number\nnew.student@example.edu,New,Student,student,25678\n')
            call_command('import_users', str(path), stdout=io.StringIO())
        self.assertTrue(User.objects.filter(email='new.student@example.edu').exists())
        mail.outbox.clear()
        response = self.client.post('/accounts/password/forgot/', {'email':'new.student@example.edu'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['new.student@example.edu'])
        self.assertIn('/accounts/password/reset/', mail.outbox[0].body)
