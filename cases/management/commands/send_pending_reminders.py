from django.core.management.base import BaseCommand

from cases.services import send_pending_reminders


class Command(BaseCommand):
    help = (
        "Remind administrators and authorities about cases with no action for too long. "
        "Schedule this once a day (cron on Linux, Task Scheduler on Windows)."
    )

    def handle(self, *args, **options):
        count = send_pending_reminders()
        self.stdout.write(self.style.SUCCESS(f"Sent reminders for {count} case(s)."))
