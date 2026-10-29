"""Create or update accounts with the same whole-file validation as the upload screen."""
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError
from accounts.importing import read_csv, preview_import, apply_import


class Command(BaseCommand):
    help = 'Validate and atomically import or update user accounts from a UTF-8 CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path')
        parser.add_argument('--dry-run', action='store_true', help='Validate without saving accounts.')

    def handle(self, csv_path, dry_run=False, **options):
        try:
            with open(csv_path, 'rb') as source:
                rows = read_csv(source)
            plan = preview_import(rows)
            if not dry_run and not plan['problems']:
                plan = apply_import(rows, plan['signature'])
        except (OSError, ValidationError, IntegrityError) as exc:
            raise CommandError(str(exc)) from exc
        if plan['problems']:
            for problem in plan['problems'][:100]:
                self.stderr.write(f"Line {problem['line']}: {' '.join(problem['errors'])}")
            raise CommandError('Import cancelled. No accounts were changed.')
        verb = 'Would create' if dry_run else 'Created'
        self.stdout.write(self.style.SUCCESS(f"{verb} {plan['created']} and updated {plan['updated']} user(s)."))
