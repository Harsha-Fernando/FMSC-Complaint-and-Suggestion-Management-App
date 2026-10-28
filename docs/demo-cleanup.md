# Retiring legacy demo cases

The old `seed_demo` command has been removed. New installations do not generate sample cases, assignments, comments, or notifications.

The cleanup command recognizes the original 16 sample cases using the title, description hash, location, demo reporter address, and the seed script's exact creation-audit/submission timestamp signature. A real submission with a similar title is preserved. Accounts, categories, units, and sequential case counters are retained; case numbers are not reused.

```sh
python manage.py remove_demo_data             # preview only
python manage.py remove_demo_data --apply     # archive first, then remove
```

The apply command creates a private recovery ZIP under `.local-backups/` containing the removed case records, their audit/comments/notifications, attachment metadata, and attached files. Only after the archive is written does it remove matching records inside a database transaction, followed by their files. Recovery archives are excluded from source control and must remain outside the served media directory. The cleanup command is repeatable: a subsequent run finds no remaining samples.

Recovery, if needed: stop writes, take a current database/media backup, extract `records.json`, and load it using `python manage.py loaddata /path/to/records.json`; restore the archive's `media/` contents into `MEDIA_ROOT`. Restore only to the same installation with its retained users/categories/authorities, and inspect primary-key collisions first. The archive is a recovery mechanism, not an in-app undo feature.

Local cleanup on 25 October 2026 removed FMSC-2026-001 through FMSC-2026-016 and their related data. FMSC-2026-017 (Broken Chair), its evidence and notification, all 11 accounts, categories, and units were preserved. The recovery archive is stored in `.local-backups/`.
