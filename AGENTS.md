# Project rules

- Keep the proposal's six roles and manual case assignment. Enforce permissions on the server, including attachments and exports.
- Preserve the official university colours: maroon `#800000` and yellow `#FFEE0C`. Use flat colours throughout; never introduce gradients, including chart fills.
- Reduce cognitive load: prioritize the next action, progressively disclose secondary information, and use concise language.
- Use shared Django templates and small, independent JavaScript modules. All essential workflows must work without JavaScript.
- Support keyboard navigation, visible focus, mobile screens, and reduced motion.
- Add requirement-based tests before fixing a defect. Fix the application when a valid test fails; do not weaken assertions to hide failures.
- Verify all six roles and cross-unit privacy after workflow or permission changes.
- Remove replaced, unused implementation in the same change. Do not remove migrations or useful regression tests as legacy code.
- Keep README.md and docs/ current with changes to setup, architecture, workflows, and validation.
- Never use production data as test fixtures. Preserve real submissions during demo cleanup; use a backup and explicit case identifiers.
- Keep English, Sinhala and Tamil UI support complete. Mark new UI strings for gettext, use named placeholders/plurals, and update both catalogs; never translate identifiers or user-entered content.
