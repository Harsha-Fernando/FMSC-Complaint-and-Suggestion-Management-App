"""Proposal §§6, 11–12, AC14/16/21: independently exercise all six roles."""
from django.urls import reverse
from accounts.models import User
from cases.models import Notification, Status
from .helpers import CaseTestCase, PASSWORD, jpeg


class RoleAccessTests(CaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.sysadmin = User.objects.create_superuser(
            username='system@example.edu', email='system@example.edu', password=PASSWORD,
            role=User.Role.SYSADMIN,
        )

    def assert_pages(self, user, allowed, forbidden):
        self.client.force_login(user)
        for url in allowed:
            with self.subTest(role=user.role, url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        for url in forbidden:
            with self.subTest(role=user.role, url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_student_has_submission_and_own_case_access(self):
        self.assert_pages(self.student, ['/', '/cases/new/', '/cases/mine/', '/notifications/'],
                          ['/dashboard/', '/work-queue/', '/reports/', '/settings/authorities/'])

    def test_lecturer_has_submission_and_own_case_access(self):
        self.assert_pages(self.lecturer, ['/', '/cases/new/', '/cases/mine/', '/notifications/'],
                          ['/dashboard/', '/work-queue/', '/reports/', '/settings/categories/'])
        case = self.submit(self.student, images=[jpeg()])
        self.client.force_login(self.lecturer)
        self.assertEqual(self.client.get(case.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(case.attachments.first().get_absolute_url()).status_code, 404)

    def test_administrator_can_review_and_assign_but_not_submit(self):
        case = self.submit()
        self.assert_pages(self.admin, ['/dashboard/', '/reports/', '/dashboard/management/',
                          '/settings/authorities/', '/settings/categories/', case.get_absolute_url()],
                          ['/cases/new/', '/cases/mine/', '/work-queue/'])
        self.assign(case, self.it_unit)
        case.refresh_from_db()
        self.assertEqual(case.assigned_authority, self.it_unit)

    def test_authority_cannot_see_unassigned_or_other_units_cases(self):
        fresh = self.submit(title='Unassigned complaint')
        other = self.assign(self.submit(title='IT complaint'), self.it_unit)
        mine = self.assign(self.submit(title='Maintenance complaint', images=[jpeg()]), self.maintenance)
        self.assert_pages(self.officer, ['/work-queue/', mine.get_absolute_url()],
                          ['/dashboard/', '/reports/', '/settings/authorities/', '/cases/new/'])
        self.assertContains(self.client.get('/work-queue/'), mine.title)
        self.assertNotContains(self.client.get('/work-queue/'), fresh.title)
        self.assertNotContains(self.client.get('/work-queue/'), other.title)
        for case in [fresh, other]:
            self.assertEqual(self.client.get(case.get_absolute_url()).status_code, 404)
            self.assertEqual(self.client.post(f'{case.get_absolute_url()}progress/', {'new_status':'solved'}).status_code, 404)

    def test_faculty_management_is_read_only(self):
        case = self.assign(self.submit(), self.maintenance)
        self.assert_pages(self.manager, ['/dashboard/', '/dashboard/management/', '/reports/', case.get_absolute_url()],
                          ['/cases/new/', '/settings/categories/', '/settings/authorities/', '/work-queue/'])
        for action in ['review', 'reject', 'close', 'reopen', 'solve']:
            self.assertEqual(self.client.post(f'{case.get_absolute_url()}{action}/', {}).status_code, 403)
        self.assertNotContains(self.client.get(case.get_absolute_url()), 'Assign case</button>')
        case.refresh_from_db()
        self.assertEqual(case.status, Status.ASSIGNED)

    def test_system_administrator_can_manage_real_users(self):
        self.assert_pages(self.sysadmin, ['/system-admin/', '/system-admin/accounts/user/',
                          '/system-admin/accounts/user/add/', '/dashboard/', '/settings/authorities/'],
                          ['/cases/new/', '/work-queue/'])
        response = self.client.post('/system-admin/accounts/user/add/', {
            'email': 'new.officer@university.example', 'first_name':'New', 'last_name':'Officer',
            'role':User.Role.AUTHORITY, 'authority':self.it_unit.pk,
            'password1':'Secure-Account-2026!', 'password2':'Secure-Account-2026!', '_save':'Save',
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='new.officer@university.example')
        self.assertEqual(user.role, User.Role.AUTHORITY)
        self.assertEqual(user.authority, self.it_unit)
        self.assertTrue(self.client.login(username=user.email, password='Secure-Account-2026!'))
        self.assertRedirects(self.client.get('/'), '/work-queue/')

    def test_new_submission_never_auto_assigns_even_with_posted_authority(self):
        case = self.submit(assigned_authority=self.maintenance.pk, authority=self.maintenance.pk, status='assigned')
        self.assertIsNone(case.assigned_authority)
        self.assertEqual(case.status, Status.SUBMITTED)
        self.assertFalse(case.audit_logs.filter(action='assigned').exists())
        self.assertTrue(Notification.objects.filter(case=case, recipient=self.admin, notification_type='new_case').exists())
        self.assertFalse(Notification.objects.filter(case=case, recipient=self.officer).exists())

    def test_reassignment_revokes_previous_units_case_and_file_access(self):
        case = self.assign(self.submit(images=[jpeg()]), self.maintenance)
        file_url = case.attachments.first().get_absolute_url()
        self.assign(case, self.it_unit)
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get(case.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(file_url).status_code, 404)
        self.client.force_login(self.it_officer)
        self.assertEqual(self.client.get(file_url).status_code, 200)

    def test_anonymous_users_cannot_read_live_notification_count(self):
        self.assertEqual(self.client.get('/notifications/summary/').status_code, 302)

    def test_live_notifications_are_personal_and_mark_read(self):
        case = self.submit()
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get('/notifications/summary/').json(), {'unread_count':0})
        self.client.force_login(self.admin)
        response = self.client.get('/notifications/summary/')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response.json(), {'unread_count':1})
        self.client.post('/notifications/read-all/')
        self.assertEqual(self.client.get('/notifications/summary/').json(), {'unread_count':0})
        self.assign(case, self.maintenance)
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get('/notifications/summary/').json(), {'unread_count':1})
        note = Notification.objects.get(case=case, recipient=self.officer)
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse('cases:notification_open', args=[note.pk])).status_code, 404)
        note.refresh_from_db()
        self.assertFalse(note.is_read)

    def test_new_system_administrator_can_open_user_management(self):
        self.client.force_login(self.sysadmin)
        response = self.client.post('/system-admin/accounts/user/add/', {
            'email':'second.system@example.edu', 'first_name':'Second', 'last_name':'Admin',
            'role':User.Role.SYSADMIN, 'password1':'Secure-System-2026!',
            'password2':'Secure-System-2026!', '_save':'Save',
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='second.system@example.edu')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/system-admin/accounts/user/').status_code, 200)
