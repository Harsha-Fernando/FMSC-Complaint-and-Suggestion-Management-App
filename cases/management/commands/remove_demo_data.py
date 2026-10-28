"""Retire only positively identified legacy sample cases, preserving all accounts."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from cases.models import Attachment, AuditLog, Case, Comment, Notification


class Command(BaseCommand):
    help = "Preview removal of legacy sample cases. --apply creates a recovery archive before removal."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--backup-dir', default=str(settings.BASE_DIR / '.local-backups'))

    def handle(self, *args, **options):
        manifest_path = Path(__file__).resolve().parents[2] / 'maintenance' / 'demo_manifest.json'
        fingerprints = {(x['title'], x['description_sha256'], x['location'])
                        for x in json.loads(manifest_path.read_text())}
        # The retired seed command backdated the creation audit to EXACTLY the
        # submission timestamp. Ordinary submissions have different timestamps.
        seeded_ids = AuditLog.objects.filter(
            action=AuditLog.Action.CREATED, created_at=F('case__submitted_at'),
            user__email__endswith='@fmsc.demo',
        ).values_list('case_id', flat=True)
        candidates = Case.objects.filter(pk__in=seeded_ids, submitted_by__email__endswith='@fmsc.demo')
        ids = [c.pk for c in candidates if
               (c.title, hashlib.sha256(c.description.encode()).hexdigest(), c.location) in fingerprints]
        cases = Case.objects.filter(pk__in=ids).order_by('pk')
        for case in cases:
            self.stdout.write(f'{case.case_number}: {case.title}')
        self.stdout.write(f'{len(ids)} legacy sample cases identified. Accounts and configuration are retained.')
        if not ids or not options['apply']:
            if ids:
                self.stdout.write('Preview only. Run with --apply to archive and remove these cases.')
            return
        backup_dir = Path(options['backup_dir']).resolve()
        media_root = Path(settings.MEDIA_ROOT).resolve()
        if backup_dir == media_root or media_root in backup_dir.parents:
            raise CommandError('Recovery archives must be outside MEDIA_ROOT.')
        backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        archive = backup_dir / f'legacy-demo-{timezone.now():%Y%m%dT%H%M%S%f}.zip'
        files = []
        with transaction.atomic():
            list(cases.select_for_update())
            attachments = Attachment.objects.filter(case_id__in=ids)
            models = [cases, attachments, Comment.objects.filter(case_id__in=ids),
                      Notification.objects.filter(case_id__in=ids), AuditLog.objects.filter(case_id__in=ids)]
            records = [obj for queryset in models for obj in queryset]
            with ZipFile(archive, 'x', compression=ZIP_DEFLATED) as backup:
                backup.writestr('records.json', serializers.serialize('json', records))
                for attachment in attachments:
                    field = attachment.file
                    if field and field.storage.exists(field.name):
                        with field.open('rb') as source:
                            backup.writestr(f'media/{field.name}', source.read())
                        files.append((field.storage, field.name))
            archive.chmod(0o600)
            # Audit records are otherwise protected from deletion. This command
            # is deliberately limited to archived legacy seed fingerprints.
            AuditLog.objects.filter(case_id__in=ids).delete()
            cases.delete()
        for storage, name in files:
            storage.delete(name)
        self.stdout.write(self.style.SUCCESS(f'Removed {len(ids)} sample cases. Recovery archive: {archive}'))
