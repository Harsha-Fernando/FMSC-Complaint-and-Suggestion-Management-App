"""Roster onboarding: unique IDs, preview/confirm, atomicity and least privilege."""
import io
import re
from datetime import timedelta
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone
from accounts.models import User
from cases.tests.helpers import CaseTestCase, PASSWORD

HEADER = 'email,first_name,last_name,role,cpm_number,lecturer_id,registration_number,department\n'
STUDENT = 'roster.student@example.edu,New,Student,student,01234,,FMSC/2026/001,Accounting\n'
LECTURER = 'roster.lecturer@example.edu,New,Lecturer,lecturer,,lec-001,,Accounting\n'
URL = '/system-admin/accounts/user/import/'

class AccountImportTests(CaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.system = User.objects.create_superuser(username='roster.system',email='roster.system@example.edu',password=PASSWORD,role=User.Role.SYSADMIN)

    def upload(self, text):
        return self.client.post(URL, {'csv_file':SimpleUploadedFile('roster.csv',text.encode('utf-8'),content_type='text/csv')})

    def preview(self, text=HEADER+STUDENT+LECTURER):
        self.client.force_login(self.system)
        response=self.upload(text)
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.context['problems'])
        return response

    def confirm(self, response):
        return self.client.post(URL,{'action':'confirm','token':response.context['token']})

    def test_preview_does_not_create_accounts_and_confirmation_preserves_identifiers(self):
        before=User.objects.count()
        response=self.preview()
        self.assertEqual(User.objects.count(),before)
        self.assertContains(response,'01234')
        self.assertEqual(self.confirm(response).status_code,302)
        student=User.objects.get(email='roster.student@example.edu')
        lecturer=User.objects.get(email='roster.lecturer@example.edu')
        self.assertEqual(student.cpm_number,'01234')
        self.assertEqual(lecturer.lecturer_id,'LEC-001')
        self.assertFalse(student.is_staff)
        self.assertFalse(student.is_superuser)
        self.assertFalse(student.has_usable_password())
        self.assertTrue(student.needs_password_setup)
        self.assertFalse(self.client.login(username=student.email,password=''))
        mail.outbox.clear()
        self.client.post('/accounts/password/forgot/',{'email':student.email})
        self.assertEqual(len(mail.outbox),1)
        self.assertIn('/accounts/password/reset/',mail.outbox[0].body)
        setup_url=re.search(r'/accounts/password/reset/\S+',mail.outbox[0].body).group(0)
        landing=self.client.get(setup_url,follow=True)
        self.assertContains(landing,'new_password1')
        self.assertEqual(self.client.post(landing.redirect_chain[-1][0],{'new_password1':PASSWORD,'new_password2':PASSWORD}).status_code,302)
        student.refresh_from_db()
        self.assertFalse(student.needs_password_setup)
        self.assertTrue(self.client.login(username=student.email,password=PASSWORD))

    def test_reimport_updates_details_but_retains_password_activity_and_cases(self):
        case=self.submit()
        self.student.cpm_number='25678'
        self.student.is_active=False
        self.student.save()
        original=self.student.password
        response=self.preview(HEADER+'student@example.edu,Updated,Name,student,25678,,FMSC/2024/0001,Finance\n')
        self.assertEqual(self.confirm(response).status_code,302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.password,original)
        self.assertFalse(self.student.is_active)
        self.assertEqual(self.student.first_name,'Updated')
        case.refresh_from_db()
        self.assertEqual(case.submitted_by_id,self.student.pk)

    def test_invalid_file_saves_nothing_and_explains_rows(self):
        self.client.force_login(self.system)
        for text in [HEADER+STUDENT+STUDENT, HEADER+STUDENT+LECTURER.replace('lec-001',''),
                     HEADER+STUDENT.replace('01234','1234'), HEADER+STUDENT.replace('01234','１２３４５'),
                     HEADER+STUDENT.replace('01234','123456'), HEADER+STUDENT.replace('student,','sysadmin,'),
                     HEADER+STUDENT.replace('student,','lecturer,'), HEADER+STUDENT.replace('roster.student@example.edu','bad-email'),
                     'wrong,headers\na,b\n', HEADER]:
            with self.subTest(text=text):
                response=self.upload(text)
                self.assertEqual(response.status_code,200)
                self.assertTrue(response.context['problems'])
                self.assertNotContains(response,'name="action" value="confirm"')
        self.assertFalse(User.objects.filter(email__startswith='roster.student').exists())

    def test_identifiers_cannot_be_transferred_to_another_person_or_role(self):
        self.student.cpm_number='01234'; self.student.save()
        response=self.preview(HEADER+LECTURER)
        self.confirm(response)
        self.client.force_login(self.system)
        for text in [HEADER+STUDENT,HEADER+LECTURER.replace('roster.lecturer','another.lecturer'),
                     HEADER+STUDENT.replace('roster.student@example.edu','student@example.edu').replace('student,','lecturer,').replace('01234,',',LEC-002')]:
            response=self.upload(text)
            self.assertTrue(response.context['problems'])

    def test_database_rejects_duplicate_cpm_and_case_insensitive_lecturer_ids(self):
        self.student.cpm_number='25678'; self.student.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(username='duplicate.cpm',email='duplicate.cpm@example.edu',cpm_number='25678')
        self.lecturer.lecturer_id='LEC-101'; self.lecturer.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.bulk_create([User(username='duplicate.lec',email='duplicate.lec@example.edu',role='lecturer',lecturer_id='lec-101')])

    def test_manual_model_validation_requires_role_identifier_and_correct_format(self):
        for role,extra in [('student',{}),('student',{'cpm_number':'abc12'}),('lecturer',{}),('lecturer',{'lecturer_id':'LEC 001'})]:
            with self.subTest(role=role,extra=extra):
                with self.assertRaises(ValidationError) as caught:
                    User(username='invalid',email='invalid@example.edu',role=role,**extra).full_clean()
                self.assertIn('cpm_number' if role=='student' else 'lecturer_id', caught.exception.message_dict)

    def test_all_six_roles_are_checked_on_get_upload_template_and_confirmation(self):
        response=self.preview()
        for user in [self.student,self.lecturer,self.admin,self.officer,self.manager]:
            self.client.force_login(user)
            for url in [URL,URL+'template/']:
                self.assertEqual(self.client.get(url).status_code,403)
            self.assertEqual(self.upload(HEADER+STUDENT).status_code,403)
            self.assertEqual(self.confirm(response).status_code,403)
        self.assertFalse(User.objects.filter(email='roster.student@example.edu').exists())
        self.client.logout()
        self.assertEqual(self.client.get(URL).status_code,302)

    def test_stale_modified_expired_and_replayed_previews_do_not_write(self):
        response=self.preview()
        self.assertEqual(self.client.post(URL,{'action':'confirm','token':'tampered'}).status_code,400)
        User.objects.create(username='conflict',email='conflict@example.edu',cpm_number='01234')
        failed=self.confirm(response)
        self.assertEqual(failed.status_code,200)
        self.assertTrue(failed.context['problems'])
        self.assertFalse(User.objects.filter(email='roster.lecturer@example.edu').exists())
        response=self.preview(HEADER+LECTURER)
        session=self.client.session
        session['account_import']['created_at']=(timezone.now()-timedelta(hours=1)).timestamp()
        session.save()
        self.assertEqual(self.confirm(response).status_code,400)
        response=self.preview(HEADER+LECTURER)
        self.assertEqual(self.confirm(response).status_code,302)
        self.assertEqual(self.confirm(response).status_code,400)

    def test_changed_target_requires_a_new_preview(self):
        self.student.cpm_number='25678'; self.student.save()
        response=self.preview(HEADER+'student@example.edu,Updated,Student,student,25678,,,Finance\n')
        User.objects.filter(pk=self.student.pk).update(department='Changed after preview')
        result=self.confirm(response)
        self.assertTrue(result.context['problems'])
        self.student.refresh_from_db()
        self.assertEqual(self.student.department,'Changed after preview')

    def test_password_setup_excludes_disabled_and_other_unusable_accounts(self):
        response=self.preview()
        self.confirm(response)
        student=User.objects.get(email='roster.student@example.edu')
        lecturer=User.objects.get(email='roster.lecturer@example.edu')
        student.set_unusable_password()
        student.save()
        lecturer.is_active=False
        lecturer.save()
        for email in [student.email,lecturer.email]:
            mail.outbox.clear()
            self.client.post('/accounts/password/forgot/',{'email':email})
            self.assertEqual(mail.outbox,[])

    def test_manual_admin_form_requires_and_saves_the_institutional_ids(self):
        self.client.force_login(self.system)
        url='/system-admin/accounts/user/add/'
        for role,field,value in [('student','cpm_number','25678'),('lecturer','lecturer_id','lec-2026')]:
            data={'email':f'manual.{role}@example.edu','first_name':'Manual','role':role,
                  'password1':'Secure-Account-2026!','password2':'Secure-Account-2026!','_save':'Save'}
            response=self.client.post(url,data)
            self.assertEqual(response.status_code,200)
            self.assertIn(field,response.context['adminform'].form.errors)
            data[field]=value
            self.assertEqual(self.client.post(url,data).status_code,302)
            user=User.objects.get(email=data['email'])
            self.assertEqual(getattr(user,field),value.upper())
            self.assertFalse(user.is_staff)
            self.assertFalse(user.is_superuser)

    def test_confirmation_requires_csrf(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.system)
        self.assertEqual(client.post(URL,{'action':'confirm','token':'x'}).status_code,403)

    def test_template_download_and_localized_preview(self):
        self.client.force_login(self.system)
        response=self.client.get(URL+'template/')
        self.assertEqual(response.status_code,200)
        self.assertIn('cpm_number,lecturer_id',response.content.decode())
        for code,heading in [('en','Import accounts'),('si','ගිණුම් ආයාත කරන්න'),('ta','கணக்குகளை இறக்குமதி செய்க')]:
            self.client.post('/i18n/setlang/',{'language':code,'next':URL})
            response=self.upload(HEADER+STUDENT+LECTURER)
            self.assertContains(response,heading)
            self.assertContains(response,'01234')
            self.assertContains(response,'LEC-001')

    def test_import_command_uses_same_atomic_validation_and_dry_run(self):
        import tempfile
        from pathlib import Path
        from django.core.management.base import CommandError
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'roster.csv'
            path.write_text(HEADER+STUDENT+LECTURER)
            call_command('import_users',str(path),dry_run=True,stdout=io.StringIO())
            self.assertFalse(User.objects.filter(email='roster.student@example.edu').exists())
            path.write_text(HEADER+STUDENT+STUDENT)
            with self.assertRaises(CommandError):
                call_command('import_users',str(path),stdout=io.StringIO())
            self.assertFalse(User.objects.filter(email='roster.student@example.edu').exists())

    def test_large_roster_validation_uses_bounded_queries(self):
        from accounts.importing import preview_import, apply_import
        rows=[{'email':f'roster{i}@example.edu','role':'student','cpm_number':f'{i:05d}'} for i in range(8000)]
        with self.assertNumQueries(2):
            plan=preview_import(rows,allowed_roles={'student','lecturer'})
        self.assertEqual(plan['created'],8000)
        self.assertEqual(plan['problems'],[])
        result=apply_import(rows,plan['signature'],allowed_roles={'student','lecturer'})
        self.assertEqual(result['problems'],[])
        self.assertEqual(User.objects.filter(email__startswith='roster',role='student').count(),8000)
        self.assertFalse(User.objects.filter(email='roster0@example.edu').get().has_usable_password())
