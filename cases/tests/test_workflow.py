"""Rules from Section 8 (case lifecycle) and Section 11 that sit outside the acceptance list."""

from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from accounts.models import User
from cases import services
from cases.models import Case, Comment, Notification, Status

from .helpers import CaseTestCase


class LifecycleRules(CaseTestCase):
    def test_close_then_reopen_goes_back_to_the_authority(self):
        case = self.assign(self.submit(), self.maintenance)
        self.progress(case, new_status="solved", resolution_note="Fixed.")
        self.login(self.admin)
        self.client.post(f"/cases/{case.case_number}/close/", {"note": "Checked on site."})
        case.refresh_from_db()
        self.assertEqual(case.status, Status.CLOSED)
        self.assertIsNotNone(case.closed_at)

        self.client.post(f"/cases/{case.case_number}/reopen/", {"reason": "Leaking again after rain."})
        case.refresh_from_db()
        self.assertEqual(case.status, Status.REOPENED)
        self.assertIsNone(case.closed_at)
        self.assertTrue(Notification.objects.filter(case=case, recipient=self.officer,
                                                    message__contains="reopened").exists())
        response = self.progress(case, comment="Back on site.")
        self.assertEqual(response.status_code, 302)
        case.refresh_from_db()
        self.assertEqual(case.status, Status.IN_PROGRESS)

    def test_only_solved_cases_can_be_closed(self):
        case = self.assign(self.submit(), self.maintenance)
        self.login(self.admin)
        response = self.client.post(f"/cases/{case.case_number}/close/", {"note": ""})
        self.assertEqual(response.status_code, 409)
        case.refresh_from_db()
        self.assertEqual(case.status, Status.ASSIGNED)

    def test_rejected_cases_cannot_be_assigned(self):
        case = self.submit()
        services.reject_case(case, self.admin, "invalid", "")
        with self.assertRaises(services.WorkflowError):
            services.assign_case(case, self.admin, self.maintenance)

    def test_authority_cannot_jump_back_to_submitted(self):
        case = self.assign(self.submit(), self.maintenance)
        response = self.progress(case, new_status="submitted")
        self.assertEqual(response.status_code, 400)

    def test_information_request_must_be_visible(self):
        case = self.assign(self.submit(), self.maintenance)
        with self.assertRaises(services.WorkflowError):
            services.update_progress(case, self.officer, new_status=Status.WAITING_INFO,
                                     comment="Which room?", is_internal=True, resolution_note="", files=[])

    def test_reporter_feedback_on_a_solved_case_alerts_admins(self):
        case = self.assign(self.submit(), self.maintenance)
        self.progress(case, new_status="solved", resolution_note="Fixed.")
        self.login(self.student)
        self.client.post(f"/cases/{case.case_number}/feedback/", {"text": "Still leaking."})
        self.assertTrue(Comment.objects.filter(case=case, comment_type="feedback").exists())
        self.assertTrue(Notification.objects.filter(case=case, recipient=self.admin,
                                                    notification_type=Notification.Type.FEEDBACK).exists())
        self.login(self.admin)
        self.assertContains(self.client.get(case.get_absolute_url()), "The reporter says this is not resolved")

    def test_every_change_is_in_the_audit_trail(self):
        case = self.assign(self.submit(), self.maintenance)
        self.progress(case, new_status="solved", resolution_note="Fixed.")
        statuses = list(case.audit_logs.filter(field="status").values_list("new_value", flat=True))
        self.assertEqual(statuses, ["Assigned", "Solved"])
        self.assertTrue(case.audit_logs.filter(action="created").exists())
        self.assertTrue(case.audit_logs.filter(action="assigned", new_value="Maintenance Division").exists())

    def test_assignment_emails_the_authority_address(self):
        case = self.submit()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.assign(case, self.maintenance)
        recipients = {address for message in mail.outbox for address in message.to}
        self.assertIn("works@example.edu", recipients)
        self.assertIn(self.officer.email, recipients)


class Reminders(CaseTestCase):
    def test_overdue_cases_are_reminded_once_a_day(self):
        overdue = self.assign(self.submit(priority="normal"), self.maintenance)
        fresh = self.assign(self.submit(priority="normal", title="Fresh"), self.maintenance)
        Case.objects.filter(pk=overdue.pk).update(submitted_at=timezone.now() - timedelta(days=5))

        call_command("send_pending_reminders", verbosity=0)
        reminders = Notification.objects.filter(notification_type=Notification.Type.REMINDER)
        self.assertEqual(set(reminders.values_list("case_id", flat=True)), {overdue.pk})
        self.assertEqual(reminders.get().recipient, self.officer)
        self.assertNotIn(fresh.pk, reminders.values_list("case_id", flat=True))

        call_command("send_pending_reminders", verbosity=0)
        self.assertEqual(Notification.objects.filter(notification_type=Notification.Type.REMINDER).count(), 1)

    def test_unreviewed_urgent_case_reminds_admins(self):
        case = self.submit(priority="urgent")
        Case.objects.filter(pk=case.pk).update(submitted_at=timezone.now() - timedelta(days=2))
        services.send_pending_reminders()
        self.assertTrue(Notification.objects.filter(case=case, recipient=self.admin,
                                                    notification_type=Notification.Type.REMINDER).exists())


class SignIn(CaseTestCase):
    def test_login_with_registration_number(self):
        response = self.client.post("/accounts/login/", {"username": "fmsc/2024/0001", "password": "Test@pass-2026"})
        self.assertEqual(response.status_code, 302)

    def test_wrong_password_is_refused(self):
        response = self.client.post("/accounts/login/", {"username": self.student.email, "password": "nope"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not right")

    def test_inactive_user_cannot_sign_in(self):
        User.objects.filter(pk=self.student.pk).update(is_active=False)
        self.assertFalse(self.client.login(username=self.student.email, password="Test@pass-2026"))

    def test_each_role_lands_on_its_home(self):
        expected = {self.admin: "/dashboard/", self.officer: "/work-queue/",
                    self.manager: "/dashboard/management/"}
        for user, url in expected.items():
            self.login(user)
            self.assertRedirects(self.client.get("/"), url)
        self.login(self.student)
        self.assertEqual(self.client.get("/").status_code, 200)


class CsvSafety(CaseTestCase):
    def test_formula_in_title_is_neutralised(self):
        self.submit(title="=HYPERLINK(\"http://evil\")")
        self.login(self.admin)
        body = self.client.get("/reports/?export=csv").content.decode("utf-8-sig")
        self.assertIn("'=HYPERLINK", body)
