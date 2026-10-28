# FMSC Complaint and Suggestion Management App

For the three-member allocation and source-only handoff packages, see
[team workflow](docs/team-workflow.md). Build them with `python tools/build_team_handoff.py`.

A Django implementation of the *Faculty Complaint and Suggestion Management App* proposal
(FMSC, University of Sri Jayewardenepura, version 1.0, 25 May 2026). This is the **manual
version**: every classification, assignment and status change is made by a person, exactly as
the proposal describes. AI classification is out of scope (Section 5.2).

- Django 5.2 LTS, Python 3.10 or newer
- SQLite for development, PostgreSQL for the faculty server
- Server-rendered pages, mobile-friendly, no JavaScript framework
- English, Sinhala and Tamil UI with a navbar language selector; see [language support](docs/languages.md)
- Proposal-based acceptance tests, six-role access tests, regression tests, and browser/accessibility tests

---

## 1. Run it on your computer

**Windows (PowerShell)**

```powershell
cd fmsc_cms
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

**Linux / macOS**

```bash
cd fmsc_cms
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000. For a fresh installation, sign in at `/system-admin/` using the superuser you created, change that user's application role to **System administrator**, then create your authorities, categories, and real users. No sample cases are loaded.

Existing development accounts are retained. Their role and unit determine what each person can access. See [account management](docs/user-accounts.md) for the Django admin and bulk-import workflows, and [demo cleanup](docs/demo-cleanup.md) for recoverable removal of legacy sample cases.

### University branding

The interface uses the University of Sri Jayewardenepura colours: **maroon `#800000`** for the
sidebar, buttons and links, and **yellow `#FFEE0C`** as the accent (university marks, the sign-in ribbon,
and the current step on a case). The system administration pages
(`/system-admin/`) use the same colours. All colour values are at the top of
`static/css/app.css`.

To show the official logos, save them as `static/img/usj-logo.png` (university) and, optionally,
`static/img/fmsc-logo.png` (faculty), then restart the server. They appear in the sidebar and on
the sign-in page. Download the university logo from the
[USJ branding page](https://www.sjp.ac.lk/branding-and-visual-identity/) and use it as supplied:
the [logo guidelines](https://www.sjp.ac.lk/guidelines-for-using-sjp-logo/) say not to change its
colours or distort it. The faculty office should confirm that using the logo on this system is
approved.

---

## 2. What each role can do

| Role (Section 6) | Screens | Actions |
|---|---|---|
| Student, Lecturer | Home summary (Wireframe 2), Submit (Wireframe 3), My cases, Notifications | Submit complaint or suggestion with photos and videos; reply when information is requested; tell the office if a solved case is not fixed |
| Administrator | Case dashboard (Wireframe 4), Case review (Wireframe 5), All cases / reports, Overview, Authorities, Categories | Review, change category and priority, accept, assign, reassign, reject with reason, record as solved, close, reopen |
| Relevant authority | Work queue (Wireframe 6), Case update (Wireframe 7) | Start work, add progress comments (public or internal), upload completion evidence, ask the reporter for information, mark solved with a resolution note |
| Faculty management | Overview (Wireframe 8), Case dashboard, Reports | Read only |
| System administrator | Everything the administrator has, plus `/system-admin/` | Manage users and roles; read-only case and audit records |

Privacy rules (Section 12):
- Reporters see only their own cases. Another person's case number returns "not found", not
  "forbidden", so case numbers cannot be probed.
- Authority officers see only cases assigned to their own unit.
- Internal notes (admin note for authority, internal comments) are never shown to reporters.
- Attachments are **not** in a public folder. Every file is served by a view that checks the same
  rules, with `nosniff` set.

---

## 3. Case lifecycle (Section 8)

```
Submitted ─► Under review ─► Not started ─► Assigned ─► In progress ─► Solved ─► Closed
    │              │              │             │        ▲     │          │        │
    └──────────────┴──────► Rejected            │        │  Waiting for   └─► Reopened ─┐
                                                │        │  information               │
                                                └────────┴──────◄─────────────────────┘
```

| From | To | Who | Rule |
|---|---|---|---|
| Submitted / Under review | Under review, Not started | Admin | "Save changes" on the review form |
| Submitted / Under review / Not started | Assigned | Admin | Must pick an **active** authority |
| Any open status except Solved | Assigned (reassign) | Admin | Old and new authority are both notified |
| Submitted, Under review, Not started, Assigned | Rejected | Admin | Reason required (invalid, duplicate, inappropriate, out of scope); reporter is told |
| Assigned, Reopened, In progress, Waiting | In progress, Waiting for information, Solved | Authority | Solved **requires a resolution note** (AC 17); a request for information must be visible to the reporter |
| Waiting for information | In progress | Reporter | Happens automatically when the reporter replies |
| Assigned, In progress, Waiting, Reopened | Solved | Admin | Also needs a resolution note |
| Solved | Closed | Admin | After confirming the work is done |
| Solved, Closed | Reopened | Admin | Goes back to the same authority |

Every change writes an audit entry (who, when, old value, new value). Audit entries cannot be
edited or deleted, even in `/system-admin/`.

### Notifications (Section 11)

Each one is an in-app notification **and** an email.

| Event | Who is told |
|---|---|
| New case | Administrators |
| Assigned / reassigned / reopened | Officers of the authority, plus the authority's email address |
| Any status change | The reporter |
| Solved (AC 18) | The reporter (with the resolution note) and administrators (to close it) |
| Information requested / reporter replied | Reporter / authority officers |
| Reporter says it's not fixed | Administrators |
| Pending case reminder | Admins (not yet reviewed) or the authority (assigned, not started) |

Reminders are sent by `python manage.py send_pending_reminders`. Schedule it once a day (cron on
Linux, Task Scheduler on Windows). Defaults: normal cases after 3 days, urgent after 1 day, at most
one reminder per case per day.

---

## 4. Dashboard definitions (Section 9)

| Indicator | How it is counted |
|---|---|
| Total cases | All cases submitted in the selected period |
| Attempted | Every status except *Submitted* (so a rejected case counts, because it was reviewed) |
| Not attempted | Status is *Submitted* |
| Open | Not *Closed* and not *Rejected* |
| Not started | *Not started*, *Assigned* or *Reopened*: accepted or assigned, but action has not started |
| Age in days | Calendar days from the submission date to today (open cases) |
| Urgent / normal | By the case's current priority (the admin can change the reporter's choice) |
| Authority-wise pending | Open cases per authority, split into in progress / not started / solved-not-closed |
| Average resolution time | Mean days from submission to *Solved* |
| Resolution rate | (Solved + Closed) ÷ (Total − Rejected) |

All dashboards and reports filter by date range, category, authority, priority, status and type.
Reports also export to CSV (UTF-8 with BOM, so Excel shows Sinhala and Tamil correctly).

---

## 5. Acceptance criteria → tests

Run all tests with `python manage.py test`.

| Section 17 criterion | Test class in `cases/tests/test_acceptance.py` |
|---|---|
| 11. Submit complaints and suggestions | `AC11_SubmitComplaintsAndSuggestions` |
| 12. Image and video upload within limits | `AC12_ImageAndVideoUploadWithinLimits` |
| 13. Unique case number | `AC13_UniqueCaseNumber` |
| 14. Review, assign, reject, reassign | `AC14_AdminReviewAssignRejectReassign` |
| 15. Authority list add / edit / deactivate / delete | `AC15_AuthorityListManagement` |
| 16. Authorities view and update assigned cases | `AC16_AuthoritySeesAndUpdatesAssignedCases` |
| 17. No "solved" without a resolution note | `AC17_SolvedNeedsResolutionNote` |
| 18. Informed user gets a message when solved | `AC18_InformedUserGetsSolvedMessage` |
| 19. Dashboard shows all required counts | `AC19_DashboardCounts` |
| 20. Not-started cases show age in days | `AC20_NotStartedAgeInDays` |
| 21. Role-based access to cases and attachments | `AC21_RoleBasedAccess` |
| 22. Reports filter by date, category, priority, authority, status | `AC22_ReportFilters` |

`cases/tests/test_workflow.py` covers the rest of the lifecycle, reminders, sign-in and CSV safety.

---

## 6. Configuration

Everything is read from environment variables. Copy `.env.example` for the full list.

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_DEBUG` | `true` | Set `false` on the server |
| `DJANGO_SECRET_KEY` | dev key | **Required** when debug is off |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Server host names |
| `DB_ENGINE` | `sqlite` | Set `postgres` and the `DB_*` variables for PostgreSQL |
| `MEDIA_ROOT` | `./media` | Where evidence files are stored (back this up) |
| `MAX_IMAGE_SIZE_MB` / `MAX_VIDEO_SIZE_MB` | 5 / 50 | Upload limits |
| `MAX_ATTACHMENTS_PER_UPLOAD` | 5 | Files per submission or update |
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | console | SMTP for real email |
| `SITE_URL` | `http://127.0.0.1:8000` | Used for links inside emails |
| `REMINDER_AFTER_DAYS_NORMAL` / `_URGENT` | 3 / 1 | Reminder thresholds |

Authorities and categories are edited inside the app (Authorities, Categories in the top menu), so
responsibilities can change without a code change (Section 12, maintainability).

### Creating real accounts

The system administrator can add users in `/system-admin/`, or use **Users → Import accounts** to upload a student/lecturer CSV, preview validated changes, and confirm the whole batch (up to 10,000 accounts / 5 MB). Students require unique five-digit CPM numbers; lecturers require unique lecturer IDs. The single searchable user list has a prominent role selector: student views show CPM/registration numbers, lecturer views show lecturer IDs, and authority views show units. The all-role view keeps general columns only; name headings and dark-mode contrast are improved. Existing accounts and case histories are preserved; fill their new identifiers from the approved register.

The command-line importer also supports all six roles:

```bash
python manage.py import_users users.csv --dry-run   # check first
python manage.py import_users users.csv
```

See `sample_users.csv` for the command-line columns, or download the two-role browser template. Newly imported accounts have no usable password and a pending-setup flag; people set their own
with "Forgot your password?" using their email. Importing does not send email automatically. An authority officer must have their
authority set, or their work queue stays empty.

---

## 7. Putting it on the faculty server

1. PostgreSQL database; set `DB_ENGINE=postgres` and the `DB_*` variables.
2. `DJANGO_DEBUG=false`, a long random `DJANGO_SECRET_KEY`, real `DJANGO_ALLOWED_HOSTS`.
3. `pip install -r requirements.txt gunicorn psycopg[binary]`
4. `python manage.py migrate` and `python manage.py collectstatic`
5. Run with Gunicorn behind Nginx (or Apache), with HTTPS. Serve `/static/` from `staticfiles/`.
   **Do not** serve `media/` publicly; the app checks permissions on every file.
6. Set the SMTP variables and `SITE_URL`.
7. Schedule `send_pending_reminders` daily.
8. Back up the database **and** the `media/` folder every night (Section 12, reliability).
9. Create the first system administrator: `python manage.py createsuperuser`, then set their role
   to *System administrator* in `/system-admin/`.

Note: Django's file response does not support byte-range requests, so seeking inside long videos
may not work in some browsers. With Nginx, switching to `X-Accel-Redirect` for attachments fixes
this and is faster.

---

## 8. Decisions to confirm with the faculty

The proposal leaves a few points open. These are the choices made in this build; each is a small
change if the faculty decides otherwise.

1. **"Not started"** is defined differently in Section 8 (a status before *Assigned*) and Section 9
   (accepted *or assigned*, no action yet). The app keeps the Section 8 status and uses the Section 9
   meaning for the dashboard count and ageing report.
2. **Reopening** is done by the administrator. The reporter can say a solved case is not fixed,
   which alerts the administrators, but cannot reopen it directly.
3. **Rejected cases** count as *attempted* (they were reviewed) and are excluded from *open*.
4. **Resolution rate** excludes rejected cases from the denominator.
5. **Sign-in** uses accounts stored in the app. Connecting to the university's central login (LDAP or
   SSO) would replace only the sign-in step.
6. The proposal numbers its acceptance criteria 11 to 22 instead of 1 to 12; the tests keep those
   numbers so they match the document.

Not included (out of scope or Phase 6 in the proposal): anonymous complaints, AI classification,
SMS/WhatsApp, QR codes, satisfaction ratings, automatic escalation.

---

## 9. Project layout

```text
manage.py
config/                         Project settings, root URLs, ASGI and WSGI
accounts/
  models.py, forms.py, admin.py
  views.py, urls.py              Account imports, language and authentication routes
  backends.py, importing.py      Sign-in and shared CSV validation/import service
  migrations/                   Database history (keep these)
  templates/accounts/           Authentication templates
  templates/admin/accounts/     Account-management overrides
  tests/                        Account onboarding/import/list regressions
cases/
  models.py, forms.py, admin.py
  views.py, urls.py              Case pages, submissions and workflow HTTP actions
  dashboard_views.py            Dashboards and CSV reports
  configuration_views.py        Authority/category settings
  notification_views.py         Personal notifications
  view_helpers.py               Shared lookup, pagination, history and lifecycle display
  services.py, permissions.py    Workflow rules and server-side authorization
  dashboard_data.py, messages.py, validators.py
  migrations/                   Database history (keep these)
  templates/cases/               Case, dashboard and settings templates
  templatetags/                  Shared template helpers and icons
  management/commands/          Operational commands
  tests/                        Case/workflow/role/privacy/language regressions
templates/                      Shared base, partials, errors and admin branding
static/                         Shared CSS, JavaScript, logos and licensed fonts
locale/                         Sinhala/Tamil PO sources and compiled MO catalogs
tests/browser/                  Playwright integration tests and isolated test server
docs/                           Setup, architecture, account and validation details
```

App-owned templates use Django's `APP_DIRS` discovery. Shared layouts and partials stay
in the project-level `templates/` directory. URLs and application behaviour are unchanged.
The view modules are flat and explicit; workflow rules remain in services instead of
being copied into HTTP handlers.

Local environments, databases, uploads, private recovery backups and generated test
outputs are excluded by `.gitignore`. Keep `db.sqlite3`, `media/` and `.local-backups/`
when cleaning a working installation: they contain real local data. `.venv/` is a local
runtime dependency, not project source. Node dependencies are used only for browser tests;
there is no frontend build step. Recreate test tooling with `npm ci` and
`npx playwright install chromium` when needed.


## Interface and verification

The case detail page pairs the description, evidence and history with a summary and role-specific actions. A maroon back button sits at the right of the case heading and wraps on narrow screens; the progress tracker has its own card. On narrow screens, the summary and actions appear above the content. Sign-in uses a wider form and script-aware heading sizes, natural letter spacing and self-hosted fonts so Sinhala and Tamil fit as comfortably as English.

The dashboard uses compact summary cards, shorter charts and small action tiles to keep the main overview together on desktop. Mobile layouts and expanded data tables use natural scrolling. The workspace follows the supplied dashboard reference: an institution sidebar with the official emblem, coloured summary cards, case overview and activity charts, recent cases, and role-specific quick-action tiles. It keeps the official maroon and yellow with flat colours throughout, accessible custom dropdowns, and progressive disclosure for filters and secondary metrics. The submission form fills the content area, with toggle-button choices; report sorting uses button-styled links. All counts/charts come from authorized records and update on page reload; no sample figures or invented growth percentages are shown. Notifications use real database events; the unread indicator refreshes every 30 seconds while visible. Essential forms work without JavaScript, and reduced-motion preferences are respected.

```sh
python manage.py test --verbosity 2
python manage.py check
python manage.py makemigrations --check --dry-run
npm ci
npx playwright install chromium
npm run test:ui
```

The browser suite starts its own temporary SQLite database and server on port 8765. It never seeds or modifies your working database. It covers all six roles, keyboard dropdowns, mobile layouts, evidence upload and the complete manual-assignment lifecycle, validation, no-JavaScript operation, live notification refresh, and automated WCAG checks. Screenshots and failure traces are written to `test-results/`.

See [architecture and UI decisions](docs/architecture.md), [test coverage and results](docs/testing.md), and [project maintenance rules](AGENTS.md).
