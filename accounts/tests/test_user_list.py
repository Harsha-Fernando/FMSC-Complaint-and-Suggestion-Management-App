"""One account list: discoverable role filtering and relevant columns."""
from django.urls import reverse
from accounts.models import User
from cases.tests.helpers import CaseTestCase, PASSWORD


class UserListTests(CaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.system=User.objects.create_superuser(username='list.system',email='list.system@example.edu',password=PASSWORD,role=User.Role.SYSADMIN)

    def setUp(self):
        self.client.force_login(self.system)
        self.url=reverse('admin:accounts_user_changelist')

    def test_all_accounts_keep_a_compact_general_list(self):
        response=self.client.get(self.url)
        self.assertContains(response,'class="account-role-filter"')
        self.assertContains(response,'name="role__exact"')
        fields=response.context['cl'].list_display
        self.assertIn('full_name',fields)
        self.assertIn('role',fields)
        self.assertNotIn('get_full_name',fields)
        for field in ['cpm_number','lecturer_id','registration_number','authority']:
            self.assertNotIn(field,fields)
        self.assertContains(response,'>Name</')
        self.assertContains(response,'Not specified')
        self.assertNotContains(response,'href="?department="></a>')
        self.assertEqual(response.context['cl'].queryset.count(),User.objects.count())

    def test_each_role_filters_records_and_uses_its_own_columns(self):
        for role in User.Role.values:
            with self.subTest(role=role):
                response=self.client.get(self.url,{'role__exact':role})
                self.assertEqual(response.status_code,200)
                self.assertEqual(set(response.context['cl'].queryset.values_list('role',flat=True)),{role})
                fields=response.context['cl'].list_display
                self.assertNotIn('role',fields)
                self.assertEqual('cpm_number' in fields,role=='student')
                self.assertEqual('registration_number' in fields,role=='student')
                self.assertEqual('lecturer_id' in fields,role=='lecturer')
                self.assertEqual('authority' in fields,role=='authority')
                self.assertEqual(response.context['selected_role'],role)

    def test_role_filter_retains_search_activity_and_department_and_resets_column_sort(self):
        response=self.client.get(self.url,{'q':'example','is_active__exact':'1','department':'Accounting','o':'2','p':'0'})
        preserved=response.context['role_filter_preserved']
        self.assertIn(('q','example'),preserved)
        self.assertIn(('is_active__exact','1'),preserved)
        self.assertIn(('department','Accounting'),preserved)
        self.assertFalse(any(key in {'o','p','role__exact'} for key,value in preserved))
        response=self.client.get(self.url,{'role__exact':'','q':'example','is_active__exact':'1'})
        self.assertEqual(response.status_code,302)
        self.assertIn('q=example',response['Location'])
        self.assertIn('is_active__exact=1',response['Location'])
        self.assertNotIn('role__exact',response['Location'])
        self.assertEqual(self.client.get(self.url,{'role__exact':'not-a-role'}).status_code,400)

    def test_role_filter_and_columns_are_localized(self):
        for code,label in [('en','Role'),('si','භූමිකාව'),('ta','பங்கு')]:
            self.client.post('/i18n/setlang/',{'language':code,'next':self.url})
            response=self.client.get(self.url,{'role__exact':'student'})
            self.assertContains(response,label)
            self.assertContains(response,'name="role__exact"')
            self.assertContains(response,'value="lecturer"')

    def test_other_five_roles_still_cannot_open_account_management(self):
        for user in [self.student,self.lecturer,self.admin,self.officer,self.manager]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url,{'role__exact':'student'}).status_code,302)
