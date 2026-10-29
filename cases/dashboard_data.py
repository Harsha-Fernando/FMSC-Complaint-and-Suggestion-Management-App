"""Presentation data built only from an explicitly authorized case queryset.

Shared by role dashboards; no random values, sample percentages, or client data.
"""

from django.utils.translation import gettext_lazy as gettext
from datetime import datetime, time, timedelta
from math import ceil
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from .models import Case, Status, NOT_STARTED_STATUSES, WORKING_STATUSES

def headline_counts(cases):
    """The dashboard indicators exactly as defined in the Section 9 table."""
    return cases.aggregate(
        total=Count("pk"),
        attempted=Count("pk", filter=~Q(status=Status.SUBMITTED)),
        not_attempted=Count("pk", filter=Q(status=Status.SUBMITTED)),
        open=Count("pk", filter=~Q(status__in=[Status.CLOSED, Status.REJECTED])),
        not_started=Count("pk", filter=Q(status__in=NOT_STARTED_STATUSES)),
        urgent=Count("pk", filter=Q(priority=Case.Priority.URGENT)),
        urgent_open=Count(
            "pk",
            filter=Q(priority=Case.Priority.URGENT) & ~Q(status__in=[Status.CLOSED, Status.REJECTED]),
        ),
        normal=Count("pk", filter=Q(priority=Case.Priority.NORMAL)),
        solved=Count("pk", filter=Q(status=Status.SOLVED)),
        closed=Count("pk", filter=Q(status=Status.CLOSED)),
        rejected=Count("pk", filter=Q(status=Status.REJECTED)),
        in_progress=Count("pk", filter=Q(status__in=WORKING_STATUSES)),
        complaints=Count("pk", filter=Q(case_type=Case.CaseType.COMPLAINT)),
        suggestions=Count("pk", filter=Q(case_type=Case.CaseType.SUGGESTION)),
    )



def dashboard_data(cases, *, reporter=False, authority=False, counts=None, today=None):
    """Return four headline metrics, case-type mix, and a seven-day activity chart.

    Staff 'open' follows the proposal (includes solved awaiting closure). Reporter
    and officer 'open' means work still outstanding, matching their case lists.
    Daily solved points use the actual solved timestamp, never submission dates.
    """
    counts = counts if counts is not None else headline_counts(cases)
    today = today or timezone.localdate()
    start = today - timedelta(days=6)
    tz = timezone.get_current_timezone()

    first = timezone.make_aware(datetime.combine(start, time.min), tz)
    after = timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min), tz)

    def daily(field):
        rows = (cases.filter(**{f'{field}__gte': first, f'{field}__lt': after})
                .order_by().annotate(day=TruncDate(field, tzinfo=tz))
                .values('day').annotate(n=Count('pk')))
        return {row['day']: row['n'] for row in rows}

    submitted, solved = daily('submitted_at'), daily('solved_at')
    rows = [{'date': start + timedelta(days=i),
             'submitted': submitted.get(start + timedelta(days=i), 0),
             'solved': solved.get(start + timedelta(days=i), 0)} for i in range(7)]
    step = max(1, ceil(max(max(r['submitted'], r['solved']) for r in rows) / 4))
    maximum = step * 4
    for i, row in enumerate(rows):
        row.update(x=48 + i * 88,
                   submitted_y=f"{166 - row['submitted'] / maximum * 144:.2f}",
                   solved_y=f"{166 - row['solved'] / maximum * 144:.2f}")
    total = counts['total']
    complaint_pct = round(100 * counts['complaints'] / total) if total else 0
    outstanding = counts['open'] - counts['solved'] if reporter or authority else counts['open']
    urgent = (cases.filter(priority=Case.Priority.URGENT)
              .exclude(status__in=[Status.SOLVED, Status.CLOSED, Status.REJECTED]).count()
              if reporter or authority else counts['urgent_open'])
    return {
        'counts': counts,
        'metrics': [
            {'label': gettext('Total cases'), 'value': total, 'tone': 'brand', 'icon': 'megaphone', 'detail': gettext('All your submissions') if reporter else gettext('In this view')},
            {'label': gettext('Open cases'), 'value': outstanding, 'tone': 'gold', 'icon': 'clock', 'detail': gettext('Work outstanding') if reporter or authority else gettext('Not yet closed')},
            {'label': gettext('Solved cases'), 'value': counts['solved'] + counts['closed'], 'tone': 'green', 'icon': 'check', 'detail': gettext('Solved or closed')},
            {'label': gettext('Urgent cases'), 'value': urgent, 'tone': 'red', 'icon': 'alert', 'detail': gettext('Open priority cases')},
        ],
        'complaint_pct': complaint_pct,
        'suggestion_pct': 100 - complaint_pct if total else 0,
        'complaint_share': f"{100 * counts['complaints'] / total:.2f}" if total else '0',
        'days': rows,
        'ticks': [{'value': step*i, 'y': 166 - 36*i} for i in range(5)],
        'submitted_points': ' '.join(f"{r['x']},{r['submitted_y']}" for r in rows),
        'solved_points': ' '.join(f"{r['x']},{r['solved_y']}" for r in rows),
        'period_start': start, 'period_end': today,
    }
