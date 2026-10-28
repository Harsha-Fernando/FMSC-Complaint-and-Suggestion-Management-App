# Three-member project handoff

The existing implementation is allocated to three members for review, maintenance,
and integration. This allocation does not establish who originally wrote the code.
Git setup, branches, commits and pushes are a later step.

## Open this first

Generate the handoff with `python tools/build_team_handoff.py`. The output is a new
numbered directory under `team-handoff/`; previous handoffs are preserved.

| Package | Responsibility | Contents |
| --- | --- | --- |
| Harsha.zip | Case administration and authority operations | Case detail and staff panels, authority/category configuration, server permissions and case admin, lifecycle/role/acceptance regression tests, demo cleanup tooling |
| Tharuka.zip | Accounts and reporter interface | Account authentication, roster import, account admin, account tests, submission and My cases templates, upload enhancement, account browser tests |
| Ruvin.zip | Dashboards, reports and notification delivery interface | Dashboard queries/views/templates, CSV report views, notification views/messages/context, reminder command, dashboard/report tests |
| Shared.zip | Agreed integration foundation | Project configuration, schema and migrations, mixed case views/forms/services, shared layout/styles, catalogs, shared tests and documentation |
| Complete-workspace.zip | Development reference for all three members | All allocated source files together, ready for fresh local setup |

`docs/team-ownership.json` is the exact file allocation. Each source file belongs to
one package only. `MANIFEST.json` records its owner and SHA-256 checksum. Package
ownership is a collaboration convention, not a server permission boundary.

Send Tharuka **Tharuka.zip + Complete-workspace.zip**, and Ruvin **Ruvin.zip +
Complete-workspace.zip**. Keep **Harsha.zip + Shared.zip + Complete-workspace.zip**
for coordination. Everyone should read this document from the complete workspace.

## Run and work safely

1. Extract Complete-workspace.zip into a new folder; its `source/` directory is the
   project root. Follow README.md to create a virtual environment, install dependencies,
   migrate a fresh database, and create a local administrator.
2. Read the member's OWNERSHIP.json. The member package contains their allocated files
   in the same relative paths as the project. It is a contribution package, not an
   independently runnable application.
3. Review and understand the assigned implementation. Make and test changes in the
   complete workspace. Keep a record of changed files; submit only the assigned changes
   when the Git workflow is established. Do not upload the entire development reference
   as one member's contribution.
4. Request coordination before changing another member's files or shared files. Harsha
   coordinates foundation updates; the feature owner reviews their affected integration.
5. Never replace a newer project with an old archive. These packages are the initial
   snapshot, not a synchronization system. Later changes must be integrated and reviewed.

The exports contain no working database, uploads, secrets, backups, installed dependencies,
or Git metadata. `sample_users.csv` is the existing documented import example, not an
export of local accounts. The original local application and its submissions stay intact.

## Shared integration responsibilities

Some existing files intentionally combine multiple features. They remain in Shared
instead of creating three conflicting versions or changing application behavior just
for packaging:

| Shared file/area | Coordination |
| --- | --- |
| cases/views.py | Tharuka: home/submission/My cases/replies; Harsha: case detail, staff actions and attachment access |
| cases/forms.py | Tharuka: submission/reply validation; Harsha: review/progress/configuration forms |
| cases/services.py | Harsha: state changes/audit; Tharuka: submission/replies; Ruvin: notify, recipient helpers, reporter messages and reminders |
| Models and migrations | Agree schema together; keep all existing migrations; coordinate new migration dependencies |
| URL configuration | Add routes with the relevant feature; preserve existing names and permission checks |
| templates/base.html, shared CSS/JS and partials | Coordinate navigation, styles and common controls; preserve flat maroon/yellow branding and accessibility |
| locale/ and language support | Each member marks their strings and supplies Sinhala/Tamil translations; coordinate catalog extraction/compilation |
| Shared acceptance/browser tests | All members maintain assertions covering their feature; never remove unrelated coverage |

Harsha's lifecycle calls Ruvin's notification integration, and Tharuka's submission
uses the shared workflow service. Ruvin's dashboards take authorized querysets. Keep
these contracts; no member package should duplicate models or bypass server checks.

## Review checklist by member

- **Harsha:** manual assignment only; required rejection/resolution notes; audit history;
  closure/reopening; authority reassignment revokes old unit access; attachment protection.
- **Tharuka:** account access and imports; password setup; student/lecturer submission;
  upload validation; own-case privacy; information replies and feedback.
- **Ruvin:** authorized dashboard totals and charts; report filters/export privacy;
  recipient-scoped notifications and email failure behavior; scheduled reminders.
- **Everyone:** six unchanged roles, English/Sinhala/Tamil, keyboard/mobile/reduced motion,
  essential workflows without JavaScript, requirement-based tests before defect fixes,
  and updated documentation.

## Validation

The handoff builder checks exact source coverage, unique file ownership, ZIP integrity,
archive bytes, and full reconstruction from the four disjoint source packages. It fails
if a new source file is not assigned in the ownership manifest. It copies source only;
it does not migrate, clean up, or read the working database or uploads.

Run `python manage.py test` from the complete workspace before integration. Run browser
checks using docs/testing.md when UI workflows change. Permission or workflow changes
must include six-role and cross-unit privacy checks. Do not weaken failing assertions.

When Git is configured later, publish the agreed foundation first, create Harsha,
Tharuka and Ruvin from it, and integrate the allocated contributions through PRs into
main. The foundation and individual overlays alone may not boot until dependencies
are integrated; use the complete workspace for testing this initial allocation.
