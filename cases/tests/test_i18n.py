"""Three-language UI, safe preferences, unchanged content, and localized notifications."""
from django.conf import settings
from django.test import Client
from django.utils.translation import gettext, override
from accounts.models import User
from cases.models import Case, Notification
from .helpers import CaseTestCase, PASSWORD


class LanguageTests(CaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.sysadmin = User.objects.create_superuser(username='system-lang', email='system.lang@example.edu', password=PASSWORD, role=User.Role.SYSADMIN)

    def set_language(self, code, next_url='/'):
        response = self.client.post('/i18n/setlang/', {'language':code,'next':next_url})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, code)
        return response

    def test_all_six_roles_render_in_all_three_languages(self):
        titles={'en':'FMSC Dashboard','si':'FMSC පාලක පුවරුව','ta':'FMSC முகப்பு'}
        for user in [self.student,self.lecturer,self.admin,self.officer,self.manager,self.sysadmin]:
            self.client.force_login(user)
            for code,title in titles.items():
                with self.subTest(role=user.role,language=code):
                    self.set_language(code)
                    response=self.client.get('/',follow=True)
                    self.assertEqual(response.status_code,200)
                    self.assertContains(response,f'<html lang="{code}">')
                    self.assertContains(response,title)
                    if user.is_reporter:
                        self.assertEqual(self.client.get('/reports/').status_code,403)
                    if user.is_authority_officer:
                        self.assertEqual(self.client.get('/dashboard/').status_code,403)

    def test_preference_available_before_login_and_rejects_unsupported_values(self):
        response=self.client.get('/accounts/login/')
        self.assertContains(response,'data-language-menu')
        self.set_language('ta','/accounts/login/')
        response=self.client.get('/accounts/login/')
        self.assertContains(response,'உள்நுழையவும்')
        self.assertEqual(self.client.post('/i18n/setlang/',{'language':'fr'}).status_code,400)
        self.assertEqual(self.client.cookies[settings.LANGUAGE_COOKIE_NAME].value,'ta')
        self.assertEqual(self.client.get('/i18n/setlang/').status_code,405)

    def test_language_selector_is_adjacent_to_notification_control(self):
        self.client.force_login(self.student)
        body=self.client.get('/').content.decode()
        self.assertLess(body.index('data-language-menu'),body.index('notification-link'))
        self.assertIn('data-language-menu',body[body.index('utility-actions'):body.index('notification-link')])

    def test_language_options_keep_their_native_names_in_every_language(self):
        import re
        for code in ['en', 'si', 'ta']:
            with self.subTest(language=code):
                self.set_language(code, '/accounts/login/')
                body = self.client.get('/accounts/login/').content.decode()
                for option, name in [('en', 'English'), ('si', 'සිංහල'), ('ta', 'தமிழ்')]:
                    button = re.search(r'<button[^>]*name="language"[^>]*value="' + option + r'"[^>]*>(.*?)</button>', body, re.S)
                    self.assertIsNotNone(button)
                    self.assertEqual(re.sub(r'<[^>]*>', '', button.group(1)).replace('✓', '').strip(), name)

    def test_language_change_requires_csrf_and_prevents_external_redirects(self):
        secure=Client(enforce_csrf_checks=True)
        self.assertEqual(secure.post('/i18n/setlang/',{'language':'si','next':'/'}).status_code,403)
        response=self.set_language('si','https://external.example/phishing')
        self.assertEqual(response['Location'],'/')

    def test_localized_form_does_not_translate_or_reassign_submitted_content(self):
        for code in ['en','si','ta']:
            with self.subTest(language=code):
                self.client.force_login(self.student)
                self.set_language(code)
                title=f'{code}: පුස්තකාලය — நூலகம்'
                response=self.client.post('/cases/new/',{'case_type':'complaint','priority':'normal','category':self.category.pk,'location':'Hall A','title':title,'description':'Sinhala සිංහල Tamil தமிழ் English','declaration':'on','assigned_authority':self.maintenance.pk})
                self.assertEqual(response.status_code,302)
                case=Case.objects.latest('pk')
                self.assertEqual(case.title,title)
                self.assertEqual(case.description,'Sinhala සිංහල Tamil தமிழ் English')
                self.assertEqual(case.status,'submitted')
                self.assertIsNone(case.assigned_authority)

    def test_required_errors_and_labels_are_localized(self):
        for code,label in [('si','කෙටි මාතෘකාව'),('ta','சுருக்கமான தலைப்பு')]:
            self.client.force_login(self.student)
            self.set_language(code)
            response=self.client.post('/cases/new/',{})
            self.assertContains(response,label)
            self.assertContains(response,'aria-invalid="true"')
            self.assertNotContains(response,'This field is required.')

    def test_new_notification_wording_follows_viewer_language_but_values_do_not(self):
        case=self.assign(self.submit(title='Dashboard'),self.maintenance)
        note=Notification.objects.get(case=case,recipient=self.student,notification_type='status_update')
        original=note.message
        for code,expected in [('si','ඔබේ විමසුම'),('ta','உங்கள் கோரிக்கை')]:
            with override(code):
                self.assertIn(expected,note.localized_message)
                self.assertIn('Maintenance Division',note.localized_message)
                self.assertEqual(note.message,original)
        new_case=Notification.objects.get(case=case,recipient=self.admin,notification_type='new_case')
        with override('si'):
            self.assertTrue(new_case.localized_message.endswith('Dashboard'))

    def test_notification_parameters_are_escaped_and_history_is_preserved(self):
        case=self.submit(title='<script>alert(1)</script>')
        note=Notification.objects.get(case=case,recipient=self.admin,notification_type='new_case')
        self.client.force_login(self.admin)
        self.set_language('ta')
        response=self.client.get('/notifications/')
        self.assertContains(response,'&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response,'<script>alert(1)</script>')
        self.assertIn('<script>alert(1)</script>',note.message)

    def test_javascript_catalog_is_translated_and_not_cached(self):
        self.set_language('si','/accounts/login/')
        response=self.client.get('/jsi18n/')
        self.assertEqual(response.status_code,200)
        self.assertIn('no-store',response['Cache-Control'])
        import json
        self.assertIn(json.dumps('විකල්පයක් තෝරන්න')[1:-1],response.content.decode())

    def test_english_fallback_and_existing_accounts_are_unchanged(self):
        with override('si'):
            self.assertEqual(gettext('Future message without a translation'),'Future message without a translation')
        self.client.force_login(self.student)
        roles=list(User.objects.values_list('pk','role'))
        for code in ['si','ta','en']:
            self.set_language(code)
        self.assertEqual(list(User.objects.values_list('pk','role')),roles)

    def test_system_admin_management_screens_can_switch_language(self):
        self.client.force_login(self.sysadmin)
        for code in ['si','ta']:
            self.set_language(code,'/system-admin/accounts/user/')
            response=self.client.get('/system-admin/accounts/user/')
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'data-language-menu')
