"""Reference dashboard: real metrics, local dates, and strict role scoping."""
from datetime import datetime, time, timedelta
from django.utils import timezone
from cases.dashboard_data import dashboard_data
from cases.models import Case, Status
from .helpers import CaseTestCase


class DashboardDataTests(CaseTestCase):
    def test_empty_overview_has_no_invented_counts_or_percentages(self):
        data = dashboard_data(Case.objects.none())
        self.assertEqual([m['value'] for m in data['metrics']], [0, 0, 0, 0])
        self.assertEqual(data['complaint_pct'], 0)
        self.assertEqual(data['suggestion_pct'], 0)
        self.assertEqual(len(data['days']), 7)
        self.assertTrue(all(row['submitted']==0 and row['solved']==0 for row in data['days']))
        self.assertEqual([x['value'] for x in data['ticks']], [0,1,2,3,4])

    def test_type_mix_and_metrics_reflect_stored_cases(self):
        self.submit(case_type='complaint')
        self.submit(case_type='suggestion', priority='normal')
        data = dashboard_data(Case.objects.all(), reporter=True)
        self.assertEqual(data['counts']['total'], 2)
        self.assertEqual(data['complaint_pct'], 50)
        self.assertEqual(data['suggestion_pct'], 50)
        self.assertEqual([m['value'] for m in data['metrics']], [2,2,0,1])

    def test_trend_uses_resolution_date_and_zero_fills_missing_days(self):
        case = self.submit()
        today = timezone.localdate()
        day = lambda n: timezone.make_aware(datetime.combine(today-timedelta(days=n),time(12)))
        Case.objects.filter(pk=case.pk).update(submitted_at=day(4), solved_at=day(1), status=Status.SOLVED)
        data = dashboard_data(Case.objects.all(), today=today)
        self.assertEqual([r['submitted'] for r in data['days']], [0,0,1,0,0,0,0])
        self.assertEqual([r['solved'] for r in data['days']], [0,0,0,0,0,1,0])
        self.assertEqual(data['days'][-1]['date'], today)
        reporter = dashboard_data(Case.objects.all(), reporter=True, today=today)
        self.assertEqual(reporter['metrics'][1]['value'], 0)
        self.assertEqual(data['metrics'][1]['value'], 1)  # staff: solved awaits closure

    def test_reporter_dashboard_excludes_every_other_reporters_data(self):
        self.submit(self.student, title='My private case')
        self.submit(self.other_student, title='Another private case')
        self.client.force_login(self.student)
        response = self.client.get('/')
        data = response.context['dashboard']
        self.assertEqual(data['counts']['total'], 1)
        self.assertEqual(sum(x['submitted'] for x in data['days']), 1)
        self.assertNotContains(response, 'Another private case')
        self.assertNotContains(response, 'View reports</span>')

    def test_authority_charts_include_only_assigned_unit(self):
        self.assign(self.submit(), self.maintenance)
        self.assign(self.submit(), self.it_unit)
        self.submit(title='Unassigned')
        self.client.force_login(self.officer)
        response = self.client.get('/work-queue/')
        self.assertEqual(response.context['dashboard']['counts']['total'], 1)
        self.assertEqual(sum(x['submitted'] for x in response.context['dashboard']['days']), 1)

    def test_admin_dashboard_filters_apply_to_charts_and_recent_cases(self):
        self.submit(priority='normal', title='Normal case')
        urgent = self.submit(priority='urgent', title='Urgent case')
        self.client.force_login(self.admin)
        response = self.client.get('/dashboard/?priority=urgent')
        self.assertEqual(response.context['dashboard']['counts']['total'], 1)
        self.assertEqual(list(response.context['recent']), [urgent])

    def test_quick_actions_prefill_type_but_never_assign_an_authority(self):
        self.client.force_login(self.student)
        for case_type in ['complaint','suggestion']:
            response = self.client.get('/cases/new/', {'type':case_type})
            self.assertEqual(response.context['form'].initial['case_type'], case_type)
        response = self.client.get('/cases/new/', {'type':'invalid'})
        self.assertNotIn('case_type', response.context['form'].initial)
        self.assertFalse(Case.objects.exists())
