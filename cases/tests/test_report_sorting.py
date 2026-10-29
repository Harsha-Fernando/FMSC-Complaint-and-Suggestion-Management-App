"""Sorting controls change real result order and retain filters."""
from datetime import timedelta
from django.utils import timezone
from cases.models import Case
from .helpers import CaseTestCase


class ReportSortingTests(CaseTestCase):
    def setUp(self):
        self.old = self.submit(title='Earlier normal case', priority='normal')
        self.urgent = self.submit(title='Urgent case', priority='urgent')
        self.new = self.submit(title='Latest normal case', priority='normal')
        now = timezone.now()
        for case, days in [(self.old, 3), (self.urgent, 2), (self.new, 1)]:
            Case.objects.filter(pk=case.pk).update(submitted_at=now-timedelta(days=days))
        self.client.force_login(self.admin)

    def test_each_sort_control_matches_actual_result_order(self):
        for order, expected in [('-submitted_at', [self.new.pk,self.urgent.pk,self.old.pk]),
                                ('submitted_at', [self.old.pk,self.urgent.pk,self.new.pk]),
                                ('-priority', [self.urgent.pk,self.new.pk,self.old.pk])]:
            with self.subTest(order=order):
                response = self.client.get('/reports/', {'sort':order})
                self.assertEqual([c.pk for c in response.context['page']], expected)
                self.assertEqual(response.context['sort_order'], order)

    def test_sorting_keeps_category_filter(self):
        response = self.client.get('/reports/', {'category':self.category.pk,'sort':'submitted_at'})
        self.assertEqual([c.pk for c in response.context['page']], [self.old.pk,self.urgent.pk,self.new.pk])
        self.assertContains(response, f'category={self.category.pk}&amp;sort=-priority')

    def test_unknown_sort_uses_newest(self):
        response = self.client.get('/reports/', {'sort':'unsupported'})
        self.assertEqual(response.context['sort_order'], '-submitted_at')
        self.assertEqual([c.pk for c in response.context['page']], [self.new.pk,self.urgent.pk,self.old.pk])
