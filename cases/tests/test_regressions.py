"""Requirement-based regressions; failures must be corrected in the application."""
from unittest.mock import patch
from cases import services
from cases.models import Notification
from accounts.models import User
from .helpers import CaseTestCase


class ReportingIntegrityTests(CaseTestCase):
    def test_authority_open_count_does_not_multiply_by_number_of_officers(self):
        self.assign(self.submit(), self.maintenance)
        User.objects.create(username='extra', email='extra@example.edu', role=User.Role.AUTHORITY, authority=self.maintenance)
        self.client.force_login(self.admin)
        response = self.client.get('/settings/authorities/')
        unit = next(x for x in response.context['authorities'] if x.pk == self.maintenance.pk)
        self.assertEqual(unit.open_cases, 1)
        self.assertEqual(unit.officer_count, 2)

    def test_failed_email_is_not_recorded_as_delivered(self):
        case = self.submit()
        Notification.objects.all().delete()
        with patch('cases.services.send_mail', side_effect=OSError('SMTP unavailable')):
            with self.captureOnCommitCallbacks(execute=True):
                services.notify([self.admin], case, Notification.Type.NEW_CASE, 'A real update')
        self.assertTrue(Notification.objects.filter(recipient=self.admin).exists())
        self.assertFalse(Notification.objects.get(recipient=self.admin).emailed)
