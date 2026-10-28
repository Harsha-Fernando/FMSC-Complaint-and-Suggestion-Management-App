# Architecture and interface

## Boundaries

This is a Django application with server-rendered templates. There is no frontend build step. Case state changes belong in `cases/services.py`; views validate forms, enforce the role and case-access rules, and invoke a service. Keep new workflow actions inside a transaction, write an audit event, and create notifications through `notify()`.

- `accounts/`: identity, roles, authentication, admin account management, CSV import.
- `cases/models.py`: relational records and scoped querysets.
- `cases/permissions.py`: role checks and case/file authorization.
- `cases/services.py`: transitions, notifications, timestamps, audit history, reminders.
- `accounts/views.py`, `accounts/urls.py`: account import endpoints, language preferences and Django authentication routes.
- `cases/views.py`: case submission, case pages and HTTP workflow actions.
- `cases/dashboard_views.py`, `cases/configuration_views.py`, `cases/notification_views.py`: clearly named groups of HTTP endpoints wired directly from `cases/urls.py`.
- `cases/view_helpers.py`: shared case visibility lookup, pagination, timeline and lifecycle display.
- `accounts/templates/accounts/`, `accounts/templates/admin/accounts/`: account-owned templates and admin overrides.
- `cases/templates/cases/`: namespaced case pages, dashboards and configuration forms.
- `accounts/tests/`, `cases/tests/`: app-owned backend tests; `tests/browser/`: browser integration tests and their isolated server.
- `templates/base.html`: shared workspace shell; `accounts/auth_base.html`: authentication layout.
- `templates/partials/`: reusable fields, filters, badges, uploads, pagination.
- `static/css/app.css`: shared tokens, components, layouts, responsive rules, reduced motion.
- `static/js/select.js`: independent progressive enhancement for single-select inputs.
- `static/js/workspace.js`: mobile navigation, account menu, validation focus, notification count polling.
- `static/js/upload.js`: upload validation/progress and conditional resolution fields.
- `static/js/language.js`: safe language switching and transient unsaved-form preservation.
- `cases/messages.py`: structured translatable system notifications with raw user parameters.
- `locale/`, `accounts/locale_support.py`: server/browser translations and framework extraction anchors.
- `static/css/language.css`, `static/fonts/`: language selector, responsive script typography and self-hosted licensed fonts.

Keep scripts independent and use server-rendered fields as the source of truth. Custom selects dispatch normal `change` events, so workflow enhancements do not need to know their implementation. Native forms and selects work with JavaScript disabled. Do not add a second styling layer to override abandoned components; remove replaced rules and templates.

## Roles and assignment

The six roles in proposal §6 remain unchanged. Students and lecturers submit; administrators review and assign; authority officers access only their unit's assignments; management reads dashboards/reports; system administrators manage users and configuration and retain case-administrator access in this implementation. Units such as Maintenance and IT are records, not separate role types.

Never derive assignment from category, submitted fields, or a UI-only restriction. New cases start unassigned. Enforce authority access through the scoped queryset and the attachment view. Reassignment revokes the previous unit's access.

## Interface decisions

Maroon `#800000` is the navigation and action colour; yellow `#FFEE0C` remains the university accent. Typography uses local system fonts and self-hosted Noto Sinhala/Tamil fonts, with no remote font requests. The shared sidebar groups case work separately from configuration and supports desktop collapse. Active navigation uses a maroon background without a vertical accent line. Mobile navigation is an expandable in-flow region with Escape dismissal and focus return; all links remain available without JavaScript.

Dashboards follow the supplied visual reference: an institution sidebar, prominent header, four coloured metric cards, a case-type donut, a seven-day activity chart, and a recent-cases table beside role-specific quick actions. The administrator’s review/closure queues, filters, ageing details, and complete metrics use disclosures. This reduces the initial information load without deleting required reporting. Configuration and submission screens use concise instructions. The submission form spans the content area; the former guide sidebar and its styles have been removed. Case type and priority remain keyboard-accessible native radio groups presented as toggle buttons. Reporter summaries say “Open cases” to avoid suggesting every unfinished case has started work.

Dropdowns use a labelled select-only combobox and listbox, with Arrow keys, Home/End, Enter/Space, Escape, Tab, typeahead, disabled options, form reset, focus states, and above/below positioning. Selection commits only on confirmation. The native select supplies submitted values and server validation. Never interpolate option labels or user content into HTML.

Motion uses short transform transitions for pages and opacity/transform transitions for popovers and stops with `prefers-reduced-motion`. Animations must never gate access to controls or information.

## Notifications

Notifications are created from real workflow events and scoped to the recipient. `GET /notifications/summary/` requires authentication, returns only the current user's unread count, and sends no-store cache headers. Visible pages poll every 30 seconds and refresh when the window regains focus; hidden tabs pause polling. Connection failure retains the last known count. The notifications page offers a refresh link when the unread count increases; it does not replace a form or list while the user is interacting.

This is polling, not WebSocket push. Emails are sent after database commit. Only a successful mail-backend send marks a recipient's record as emailed; failures are logged while the in-app record remains available. Real email delivery requires SMTP configuration. Reminders still require the scheduled management command.

## Data and future changes

Keep migrations; they are part of the installation and upgrade history. New features should extend services and shared components rather than duplicate role or state logic. Validate new transitions and role boundaries with tests before release. UI browser fixtures run against a temporary database, never the working database. Demo case generation has been retired; the narrow cleanup manifest exists only to identify old samples for recoverable removal.

## Dashboard presentation data

`cases/dashboard_data.py` accepts an explicitly authorized queryset and returns metric cards, complaint/suggestion proportions, and seven daily submission/resolution totals. Reporter charts use only their cases; authority charts use only their unit’s assigned cases; staff charts follow the active report filters. No global chart endpoint bypasses those scopes. Time-series queries use local-day boundaries and database aggregation over the seven-day timestamp range. Resolution activity uses `solved_at`, not the submission date. Empty days are zero-filled and empty distributions display a neutral ring.

The existing staff definition of open (includes solved awaiting closure) is preserved. Reporter/officer open counts mean outstanding work and exclude solved cases. Solved cards include solved and closed cases. No percentage growth is displayed because the reference’s illustrative growth values are not application records.

Charts are server-rendered SVG with a readable data table and no chart-library dependency. The donut uses solid SVG circle segments, not a CSS colour effect. They work without JavaScript. Shared dashboard templates are `dashboard_metrics.html`, `dashboard_charts.html`, `recent_cases.html`, and `quick_actions.html`. Quick actions prefill complaint/suggestion type using validated query values; they do not submit or assign a case. Management gets read-only navigation actions. The recent-update panel uses the signed-in user’s actual notification records.

The original university emblem is stored locally at `static/img/usj-logo.png`, downloaded unchanged from the [university branding page](https://www.sjp.ac.lk/branding-and-visual-identity/). The dark sidebar and maroon actions retain the university palette; yellow is used on gold summary/action tiles with dark text. Green/red/plum identify secondary status/action groups.

## Flat-colour and control rules

Use solid colours across the application, including navigation, avatars, metric cards, quick actions, sign-in screens, and chart segments. Gradients are prohibited in AGENTS.md. Native case-type/priority radio controls retain single-choice and keyboard semantics while their labels provide button-sized hit areas and visible selection/focus. Sorting links are styled as buttons, expose the active sort, retain report filters, and reset pagination.

Dashboard metrics and charts are recomputed from current authorized records on each page request. They do not automatically refresh in the background. Notification unread counts alone poll every 30 seconds. Browser coverage submits a real case in the temporary database and verifies that reloading increases both the total and the current day’s chart count.

## Language boundary

Django LocaleMiddleware selects the language from the supported browser preference. A CSRF-protected POST endpoint validates language codes and delegates cookie/redirect handling to Django. Templates and JavaScript share gettext catalogs. Notification metadata allows the same notification to render in each viewer’s language; user content stays unchanged. See [language support](languages.md) for maintenance, fallback and migration details.

The signed-in change-password form uses the full available content width through the shared panel layout, with no page-specific width cap.

## Compact dashboard layout

Shared summary cards use less padding; overview and trend charts have a compact height, and quick actions pair icons with text horizontally. The recent-case table retains every supplied row (six for reporters, five for staff). No fixed page height, hidden overflow or nested vertical scrolling is used to force content into the viewport. Expanded chart data, staff disclosures, long content and mobile layouts can grow naturally. A short-screen desktop media query reduces spacing further and widens the action panel for translated labels. The donut shows only the total number in this mode; the total label remains in the summary card and its proportions remain in the accessible chart description and legend. English, Sinhala and Tamil share the layout and keep their script-aware typography. Numeric summaries use tight leading independently of script labels.

## Account roster imports

The six roles remain on the shared User model. Nullable unique `cpm_number` and `lecturer_id` fields preserve legacy accounts without inventing identifiers. Student CPM values are exactly five ASCII digits; lecturer IDs are canonical uppercase and also have a database case-insensitive uniqueness constraint. Account forms and CSV validation enforce role-specific requirements. Email/registration-number authentication is unchanged.

`accounts/importing.py` validates the complete roster against two bulk lookup queries, rather than querying per row. Browser import views explicitly require active staff accounts with the system administrator role; uploading cannot create staff roles or change an existing account's role. A server-side session stores validated input, owner, confirmation token, target-state fingerprint and a 15-minute expiry. Confirmation revalidates, locks current users, detects stale targets, and performs batched creation/updates in one transaction. The command-line importer uses the same service for all six role codes. Preview and dry run do not write accounts. Existing passwords, privileges, active status, account keys and case relationships remain unchanged.

New imported accounts have unusable passwords and `needs_password_setup=True`. The application's password-reset form includes only active pending-setup accounts or active accounts with usable passwords. A password change clears the setup flag. This permits normal expiring setup links while avoiding thousands of password-hash operations during a faculty-wide import. The import itself sends no emails. See [account management](user-accounts.md) for rollout, file semantics and deployment.

## Account-list role filter

Account management remains one Django UserAdmin list and the existing `role__exact` query parameter. A labelled native GET selector moves role selection above the table. `get_list_display()` chooses compact, role-relevant columns; `get_list_filter()` offers unit filtering only for authority accounts. The all-role view shows general fields. Existing search, active and department parameters survive role selection; pagination and index-based sorting reset because column positions change. Names use a labelled, sortable display method. Admin dark/automatic-dark themes override low-contrast link and selected-row colours while retaining maroon controls and yellow accents. No schema, roles, permissions or account records change.

## Source layout and local artifacts

Each app retains the standard `apps.py`, `models.py`, `admin.py`, `forms.py`, `views.py`, `urls.py`, `migrations/`, `templates/` and `tests/` structure. Related case views stay in small, flat modules rather than a hidden re-export package or one large combined file. Account import views live directly in `accounts/views.py`. Shared layouts, fonts and static enhancements remain project-wide because both apps use them.

The obsolete `cases/views/` package, `accounts/import_views.py`, project-level app templates and old test locations were replaced in the same change. No URL names, workflow rules, roles, migrations, records or useful regression tests were removed. Framework translation extraction anchors and font licences are required source assets. The guarded legacy-demo cleanup command and its identification manifest remain operational tools.

`.gitignore` excludes private/local data, dependency folders, browser caches, bytecode and test/build output. It deliberately retains migrations, all regression tests, compiled translation catalogs, dependency lockfiles and `.env.example`. Python's local virtual environment is retained for running the app; browser-test dependencies and binaries can be reinstalled from the documented commands.
