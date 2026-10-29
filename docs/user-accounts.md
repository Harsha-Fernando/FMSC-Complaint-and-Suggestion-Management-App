# Creating and managing accounts

Only the **System administrator** manages accounts. A faculty complaint administrator manages cases, not users. There is no public self-registration.

## Upload a student or lecturer register

1. Open **Users** in the application navigation, then **Users → Import accounts** in system administration (`/system-admin/accounts/user/import/`).
2. Download the CSV template. It contains fictitious student/lecturer examples; replace those rows with the approved register.
3. Export as **UTF-8 CSV**. Keep column names unchanged and use the role codes `student` or `lecturer`.
4. Upload and select **Preview import**. Nothing is saved at this stage. The first 50 rows are displayed, with the full-file new/update totals. Every row is validated.
5. Correct reported problems and re-upload, or select **Confirm import**. The entire batch is committed together. Any validation or uniqueness conflict cancels the batch.

The upload supports **10,000 rows and 5 MB per file**. It works without JavaScript. Previews are stored in the administrator's server-side session, bound to that signed-in user and a random confirmation token, valid for 15 minutes. They are removed after confirmation, replaced on a new upload, and cleared on logout. Standard expired-session cleanup (`clearsessions`) removes expired server sessions. No public CSV upload or download location is created. Uploaded files are not retained as roster documents.

| Column | Rule |
| --- | --- |
| `email` | Required, valid and unique; matches existing accounts case-insensitively |
| `role` | Required; browser imports accept only `student` and `lecturer` |
| `cpm_number` | Required for students; exactly five ASCII digits, unique; blank for other roles |
| `lecturer_id` | Required for lecturers; unique without case sensitivity; blank for other roles |
| `first_name`, `last_name` | Optional names |
| `registration_number` | Optional, unique; existing registration-number sign-in is retained |
| `department`, `contact_number` | Optional profile details |

Lecturer IDs support ASCII letters/numbers and `.`, `-`, `_`, `/`; the first character must be a letter or digit. They are stored uppercase. Examples: `LEC-001`, `FMSC/LEC/125`. CPM numbers are strings: **01234 stays 01234**. Format CPM spreadsheet cells as text before exporting; an exported `1234` is rejected rather than guessing a missing digit.

Existing passwords, active/inactive state, privileges and case ownership are preserved. Role changes must be made individually through user management. A roster cannot transfer another user's CPM number, lecturer ID or registration number. If an email changes, correct that account individually before importing; email is the matching key. Supplied blank optional cells clear that profile value; omitted optional columns leave existing values unchanged. Imports do not deactivate users absent from a file. Account changes after preview require a fresh preview.

## Password setup

New imported users have **no usable password** and an explicit pending-setup flag. They use **Forgot your password?** with their email to receive the normal expiring password-reset link. SMTP must be configured. No passwords are uploaded, generated for distribution or emailed, and importing does not send email automatically. The reset form permits pending-setup accounts while keeping other unusable-password accounts excluded. Setting a password clears the flag. This avoids running a password hash thousands of times during roster import.

Sign-in remains email or registration number. CPM and lecturer IDs are additional institutional identifiers, not new sign-in methods.

## Create or edit an individual account

Open **Users → Add user** in `/system-admin/`. Enter email, name, role and an initial password that meets the password rules. Supply the CPM number for a student or lecturer ID for a lecturer; select the unit for an authority officer. System administrator accounts receive Django staff/superuser access through this save flow. Other roles use the main application.

Use the **Role** selector above the user table and select **Apply filters**. The same list shows general columns for all roles, CPM/registration numbers for students, lecturer IDs for lecturers, and units for authority officers. Other selected roles show their name, email, department and active status. Both institutional IDs remain searchable. Search text, active-state and department filters are retained when applying a role; pagination, column sorting and authority filters reset so they do not carry across incompatible views. The role selector works without JavaScript. Dark mode and automatic dark mode use readable link colours. Existing accounts remain intact after migration, with these new fields blank until the approved identifiers are supplied. No identifiers are invented and no case records are rewritten. Editing a student/lecturer or importing them requires the appropriate identifier.

## Command-line import

The existing command remains available for all six role codes. Use `sample_users.csv` as its column reference; the optional `authority` column must name an existing unit for authority accounts. Do not upload this mixed-role example through the student/lecturer-only browser screen.

```sh
python manage.py import_users users.csv --dry-run
python manage.py import_users users.csv
```

Both paths use the same validation and atomic batch service. `--dry-run` makes no changes. A file with any invalid row now fails in full instead of silently skipping rows. Existing account roles cannot be changed by this command either. Back up the database before a large account update.

## Deployment

Back up the database, run `python manage.py migrate`, compile the Sinhala/Tamil catalogs, collect static files, and restart application workers. Migration `accounts.0003` adds nullable unique identifiers and the pending-password-setup flag without changing existing users or submissions. The pending import uses Django's default database-backed sessions; keep server-side sessions enabled for this workflow rather than a signed-cookie session backend. Schedule normal expired-session cleanup.
