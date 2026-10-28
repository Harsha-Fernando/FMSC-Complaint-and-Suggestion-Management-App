"""One test class per acceptance criterion in Section 17 of the proposal.

The proposal numbers its criteria 11 to 22, so the classes use the same numbers.
Run with:  python manage.py test
"""

from django.core import mail
from django.test import override_settings

from cases.models import Attachment, AuditLog, Authority, Case, Notification, Status

from .helpers import CaseTestCase, jpeg, mp4


class AC11_SubmitComplaintsAndSuggestions(CaseTestCase):
    def test_student_submits_a_complaint(self):
        case = self.submit(self.student)
        self.assertEqual(case.case_type, Case.CaseType.COMPLAINT)
        self.assertEqual(case.priority, Case.Priority.URGENT)
        self.assertEqual(case.status, Status.SUBMITTED)
        self.assertEqual(case.submitted_by, self.student)
        self.assertTrue(case.declaration_accepted)

    def test_lecturer_submits_a_suggestion(self):
        case = self.submit(self.lecturer, case_type="suggestion", priority="normal",
                           title="Add benches near the library")
        self.assertEqual(case.case_type, Case.CaseType.SUGGESTION)
        self.assertEqual(case.submitted_by, self.lecturer)

    def test_declaration_is_required(self):
        self.login(self.student)
        response = self.client.post("/cases/new/", {
            "case_type": "complaint", "priority": "normal", "category": self.category.pk,
            "location": "Hall A", "title": "Broken chair", "description": "Leg broken.",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("declaration", response.context["form"].errors)
        self.assertFalse(Case.objects.exists())

    def test_staff_roles_cannot_submit(self):
        self.login(self.officer)
        self.assertEqual(self.client.get("/cases/new/").status_code, 403)

    def test_administrators_are_notified_of_a_new_case(self):
        case = self.submit(self.student)
        self.assertTrue(
            Notification.objects.filter(case=case, recipient=self.admin,
                                        notification_type=Notification.Type.NEW_CASE).exists()
        )


class AC12_ImageAndVideoUploadWithinLimits(CaseTestCase):
    def test_image_and_video_are_saved(self):
        case = self.submit(self.student, images=[jpeg()], videos=[mp4()])
        kinds = sorted(case.attachments.values_list("file_type", flat=True))
        self.assertEqual(kinds, ["image", "video"])
        self.assertTrue(all(a.file.name.startswith(f"case_files/{case.case_number}/")
                            for a in case.attachments.all()))

    @override_settings(MAX_IMAGE_SIZE_MB=0)
    def test_oversized_image_is_refused(self):
        self.login(self.student)
        response = self.client.post("/cases/new/", {
            "case_type": "complaint", "priority": "normal", "category": self.category.pk,
            "location": "Hall A", "title": "Broken chair", "description": "Leg broken.",
            "declaration": "on", "images": [jpeg()],
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("must be 0 MB or smaller", str(response.context["form"].non_field_errors()))
        self.assertFalse(Case.objects.exists())

    def test_wrong_file_type_is_refused(self):
        self.login(self.student)
        from django.core.files.uploadedfile import SimpleUploadedFile

        script = SimpleUploadedFile("photo.jpg", b"#!/bin/sh\nrm -rf /\n", content_type="image/jpeg")
        exe = SimpleUploadedFile("tool.exe", b"MZ\x90\x00", content_type="application/octet-stream")
        response = self.client.post("/cases/new/", {
            "case_type": "complaint", "priority": "normal", "category": self.category.pk,
            "location": "Hall A", "title": "Broken chair", "description": "Leg broken.",
            "declaration": "on", "images": [script, exe],
        })
        errors = str(response.context["form"].non_field_errors())
        self.assertIn("does not look like a real JPG file", errors)
        self.assertIn("not an accepted image type", errors)
        self.assertFalse(Attachment.objects.exists())

    @override_settings(MAX_ATTACHMENTS_PER_UPLOAD=2)
    def test_too_many_files_is_refused(self):
        self.login(self.student)
        response = self.client.post("/cases/new/", {
            "case_type": "complaint", "priority": "normal", "category": self.category.pk,
            "location": "Hall A", "title": "Broken chair", "description": "Leg broken.",
            "declaration": "on", "images": [jpeg("a.jpg"), jpeg("b.jpg"), jpeg("c.jpg")],
        })
        self.assertIn("at most 2 files", str(response.context["form"].non_field_errors()))


class AC13_UniqueCaseNumber(CaseTestCase):
    def test_every_case_gets_a_unique_sequential_number(self):
        first = self.submit(self.student)
        second = self.submit(self.lecturer)
        third = self.submit(self.other_student)
        numbers = [first.case_number, second.case_number, third.case_number]
        self.assertEqual(len(set(numbers)), 3)
        year = first.submitted_at.year
        self.assertEqual(numbers, [f"FMSC-{year}-001", f"FMSC-{year}-002", f"FMSC-{year}-003"])

    def test_case_number_is_shown_after_submission(self):
        self.login(self.student)
        response = self.client.post("/cases/new/", {
            "case_type": "complaint", "priority": "normal", "category": self.category.pk,
            "location": "Hall A", "title": "Broken chair", "description": "Leg broken.",
            "declaration": "on",
        }, follow=True)
        case = Case.objects.get()
        self.assertContains(response, case.case_number)


class AC14_AdminReviewAssignRejectReassign(CaseTestCase):
    def test_review_assign_and_reassign(self):
        case = self.submit()
        self.login(self.admin)
        response = self.client.post(f"/cases/{case.case_number}/review/", {
            "action": "save", "status": "under_review", "category": self.other_category.pk,
            "priority": "normal", "internal_note": "Check the ceiling too.",
        })
        self.assertEqual(response.status_code, 302)
        case.refresh_from_db()
        self.assertEqual(case.status, Status.UNDER_REVIEW)
        self.assertEqual(case.category, self.other_category)
        self.assertEqual(case.priority, Case.Priority.NORMAL)
        self.assertIsNotNone(case.reviewed_at)

        case = self.assign(case, self.maintenance)
        self.assertEqual(case.status, Status.ASSIGNED)
        self.assertEqual(case.assigned_authority, self.maintenance)

        case = self.assign(case, self.it_unit)
        self.assertEqual(case.assigned_authority, self.it_unit)
        self.assertTrue(case.audit_logs.filter(description__startswith="Reassigned from Maintenance").exists())

    def test_reject_tells_the_reporter_why(self):
        case = self.submit()
        self.login(self.admin)
        self.client.post(f"/cases/{case.case_number}/reject/", {"reason": "duplicate",
                                                                "note": "Same as FMSC-2026-001."})
        case.refresh_from_db()
        self.assertEqual(case.status, Status.REJECTED)
        note = Notification.objects.get(case=case, recipient=self.student)
        self.assertIn("Duplicate", note.message)

    def test_assign_needs_an_authority(self):
        case = self.submit()
        self.login(self.admin)
        response = self.client.post(f"/cases/{case.case_number}/review/", {
            "action": "assign", "category": case.category_id, "priority": "urgent", "internal_note": "",
        })
        self.assertEqual(response.status_code, 400)
        case.refresh_from_db()
        self.assertEqual(case.status, Status.SUBMITTED)

    def test_inactive_authority_cannot_be_chosen(self):
        self.maintenance.is_active = False
        self.maintenance.save()
        case = self.submit()
        self.login(self.admin)
        response = self.client.post(f"/cases/{case.case_number}/review/", {
            "action": "assign", "category": case.category_id, "priority": "urgent",
            "authority": self.maintenance.pk,
        })
        self.assertEqual(response.status_code, 400)

    def test_only_admins_can_assign(self):
        case = self.submit()
        for user in (self.student, self.officer, self.manager):
            self.login(user)
            response = self.client.post(f"/cases/{case.case_number}/review/", {
                "action": "assign", "category": case.category_id, "priority": "urgent",
                "authority": self.maintenance.pk,
            })
            self.assertEqual(response.status_code, 403, user.role)


class AC15_AuthorityListManagement(CaseTestCase):
    def test_add_edit_deactivate_and_delete(self):
        self.login(self.admin)
        self.client.post("/settings/authorities/new/", {"name": "Examination Unit", "email": "exams@example.edu",
                                                         "is_active": "on"})
        unit = Authority.objects.get(name="Examination Unit")
        self.client.post(f"/settings/authorities/{unit.pk}/", {"name": "Examination Branch",
                                                                "officer_name": "Ms. Silva", "is_active": "on"})
        unit.refresh_from_db()
        self.assertEqual(unit.name, "Examination Branch")
        self.client.post(f"/settings/authorities/{unit.pk}/toggle/")
        unit.refresh_from_db()
        self.assertFalse(unit.is_active)
        self.client.post(f"/settings/authorities/{unit.pk}/delete/")
        self.assertFalse(Authority.objects.filter(pk=unit.pk).exists())
        self.assertEqual(AuditLog.objects.filter(action=AuditLog.Action.CONFIG_CHANGED).count(), 4)

    def test_authority_with_history_is_kept(self):
        case = self.submit()
        self.assign(case, self.maintenance)
        self.login(self.admin)
        self.client.post(f"/settings/authorities/{self.maintenance.pk}/delete/")
        self.assertTrue(Authority.objects.filter(pk=self.maintenance.pk).exists())

    def test_reporters_and_officers_cannot_manage_the_list(self):
        for user in (self.student, self.officer, self.manager):
            self.login(user)
            self.assertEqual(self.client.get("/settings/authorities/").status_code, 403)


class AC16_AuthoritySeesAndUpdatesAssignedCases(CaseTestCase):
    def test_work_queue_and_progress_update(self):
        case = self.assign(self.submit(), self.maintenance)
        self.login(self.officer)
        queue = self.client.get("/work-queue/")
        self.assertContains(queue, case.case_number)

        response = self.progress(case, comment="Plumber booked for tomorrow.", completion_images=[jpeg()])
        self.assertEqual(response.status_code, 302)
        case.refresh_from_db()
        self.assertEqual(case.status, Status.IN_PROGRESS)
        self.assertIsNotNone(case.started_at)
        self.assertTrue(case.comments.filter(text__startswith="Plumber").exists())
        self.assertEqual(case.attachments.get().kind, Attachment.Kind.COMPLETION)

    def test_other_units_cannot_see_or_update(self):
        case = self.assign(self.submit(), self.maintenance)
        self.login(self.it_officer)
        self.assertNotContains(self.client.get("/work-queue/"), case.case_number)
        self.assertEqual(self.client.get(case.get_absolute_url()).status_code, 404)
        self.assertEqual(self.progress(case, user=self.it_officer).status_code, 404)

    def test_waiting_for_information_loop(self):
        case = self.assign(self.submit(), self.maintenance)
        self.progress(case, new_status="waiting_info", comment="Which floor exactly?")
        case.refresh_from_db()
        self.assertEqual(case.status, Status.WAITING_INFO)

        self.login(self.student)
        page = self.client.get(case.get_absolute_url())
        self.assertContains(page, "Which floor exactly?")
        self.client.post(f"/cases/{case.case_number}/reply/", {"text": "Second floor, near room 204."})
        case.refresh_from_db()
        self.assertEqual(case.status, Status.IN_PROGRESS)
        self.assertTrue(Notification.objects.filter(case=case, recipient=self.officer,
                                                    notification_type=Notification.Type.REPLY).exists())


class AC17_SolvedNeedsResolutionNote(CaseTestCase):
    def test_cannot_mark_solved_without_note(self):
        case = self.assign(self.submit(), self.maintenance)
        response = self.progress(case, new_status="solved", resolution_note="  ")
        self.assertEqual(response.status_code, 400)
        case.refresh_from_db()
        self.assertNotEqual(case.status, Status.SOLVED)

    def test_admin_also_needs_a_note(self):
        case = self.assign(self.submit(), self.maintenance)
        self.login(self.admin)
        response = self.client.post(f"/cases/{case.case_number}/solve/", {"resolution_note": ""})
        self.assertEqual(response.status_code, 400)
        case.refresh_from_db()
        self.assertEqual(case.status, Status.ASSIGNED)

    def test_note_is_stored_when_solved(self):
        case = self.assign(self.submit(), self.maintenance)
        self.progress(case, new_status="solved", resolution_note="Pipe joint resealed.")
        case.refresh_from_db()
        self.assertEqual(case.status, Status.SOLVED)
        self.assertEqual(case.resolution_note, "Pipe joint resealed.")
        self.assertIsNotNone(case.solved_at)


class AC18_InformedUserGetsSolvedMessage(CaseTestCase):
    def test_in_app_and_email_message(self):
        case = self.assign(self.submit(), self.maintenance)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.progress(case, new_status="solved", resolution_note="Pipe joint resealed.")
        note = Notification.objects.get(case=case, recipient=self.student,
                                        notification_type=Notification.Type.SOLVED)
        self.assertIn("Pipe joint resealed.", note.message)
        self.assertTrue(any(self.student.email in m.to and "solved" in m.subject.lower() for m in mail.outbox))

    def test_reporter_sees_it_in_notifications(self):
        case = self.assign(self.submit(), self.maintenance)
        self.progress(case, new_status="solved", resolution_note="Done.")
        self.login(self.student)
        self.assertContains(self.client.get("/notifications/"), "Your case has been solved")


class AC19_DashboardCounts(CaseTestCase):
    def test_counts_follow_section_9_definitions(self):
        submitted = self.submit(title="Not reviewed")
        reviewed = self.submit(title="Under review")
        assigned = self.submit(title="Assigned")
        working = self.submit(title="In progress")
        solved = self.submit(title="Solved", priority="normal")
        closed = self.submit(title="Closed", priority="normal")

        self.login(self.admin)
        self.client.post(f"/cases/{reviewed.case_number}/review/", {
            "action": "save", "status": "under_review", "category": self.category.pk, "priority": "urgent"})
        for case in (assigned, working, solved, closed):
            self.assign(case, self.maintenance)
        self.progress(working, comment="Started.")
        for case in (solved, closed):
            self.progress(case, new_status="solved", resolution_note="Fixed.")
        self.login(self.admin)
        self.client.post(f"/cases/{closed.case_number}/close/", {"note": ""})

        counts = self.client.get("/dashboard/").context["counts"]
        self.assertEqual(counts["total"], 6)
        self.assertEqual(counts["not_attempted"], 1)       # submitted only
        self.assertEqual(counts["attempted"], 5)
        self.assertEqual(counts["open"], 5)                # everything except closed
        self.assertEqual(counts["not_started"], 1)         # assigned, no action yet
        self.assertEqual(counts["urgent"], 4)
        self.assertEqual(counts["normal"], 2)
        self.assertEqual(counts["solved"], 1)
        self.assertEqual(counts["closed"], 1)
        self.assertEqual(submitted.status, Status.SUBMITTED)

    def test_management_can_view_but_not_act(self):
        case = self.submit()
        self.login(self.manager)
        self.assertEqual(self.client.get("/dashboard/").status_code, 200)
        self.assertEqual(self.client.get("/dashboard/management/").status_code, 200)
        self.assertEqual(self.client.get(case.get_absolute_url()).status_code, 200)
        response = self.client.post(f"/cases/{case.case_number}/reject/", {"reason": "invalid"})
        self.assertEqual(response.status_code, 403)


class AC20_NotStartedAgeInDays(CaseTestCase):
    def test_ageing_report_shows_days_since_submission(self):
        from datetime import timedelta

        from django.utils import timezone

        case = self.assign(self.submit(), self.maintenance)
        Case.objects.filter(pk=case.pk).update(submitted_at=timezone.now() - timedelta(days=6))
        case.refresh_from_db()
        self.assertEqual(case.age_days, 6)

        self.login(self.admin)
        response = self.client.get("/dashboard/")
        ageing = response.context["ageing"]
        self.assertEqual([c.case_number for c in ageing], [case.case_number])
        self.assertContains(response, f'<span class="age age-mid">6</span>', html=False)

    def test_started_cases_leave_the_ageing_report(self):
        case = self.assign(self.submit(), self.maintenance)
        self.progress(case, comment="On it.")
        self.login(self.admin)
        self.assertEqual(list(self.client.get("/dashboard/").context["ageing"]), [])


class AC21_RoleBasedAccess(CaseTestCase):
    def test_reporters_see_only_their_own_cases(self):
        case = self.submit(self.student, images=[jpeg()])
        attachment = case.attachments.get()
        self.login(self.other_student)
        self.assertEqual(self.client.get(case.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(attachment.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get("/cases/mine/"), case.case_number)

    def test_owner_and_staff_can_open_the_attachment(self):
        case = self.submit(self.student, images=[jpeg()])
        attachment = case.attachments.get()
        for user in (self.student, self.admin, self.manager):
            self.login(user)
            response = self.client.get(attachment.get_absolute_url())
            self.assertEqual(response.status_code, 200, user.role)
            self.assertEqual(response["Content-Type"], "image/jpeg")
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_assigned_authority_only(self):
        case = self.assign(self.submit(images=[jpeg()]), self.maintenance)
        attachment = case.attachments.get()
        self.login(self.officer)
        self.assertEqual(self.client.get(attachment.get_absolute_url()).status_code, 200)
        self.login(self.it_officer)
        self.assertEqual(self.client.get(attachment.get_absolute_url()).status_code, 404)

    def test_internal_notes_are_hidden_from_the_reporter(self):
        case = self.assign(self.submit(), self.maintenance, note="Reporter is very upset; call first.")
        self.progress(case, comment="Contractor quote is too high.", is_internal="on")
        self.login(self.student)
        page = self.client.get(case.get_absolute_url())
        self.assertNotContains(page, "call first")
        self.assertNotContains(page, "Contractor quote")
        self.login(self.officer)
        page = self.client.get(case.get_absolute_url())
        self.assertContains(page, "call first")
        self.assertContains(page, "Contractor quote")

    def test_anonymous_users_are_sent_to_login(self):
        case = self.submit()
        self.client.logout()
        response = self.client.get(case.get_absolute_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])


class AC22_ReportFilters(CaseTestCase):
    def setUp(self):
        self.leak = self.assign(self.submit(title="Leak", priority="urgent"), self.maintenance)
        self.wifi = self.assign(self.submit(title="Wi-Fi", priority="normal",
                                            category=self.other_category.pk), self.it_unit)
        self.idea = self.submit(title="Benches", case_type="suggestion", priority="normal")
        self.login(self.admin)

    def numbers(self, query):
        return {c.case_number for c in self.client.get(f"/reports/?{query}").context["page"]}

    def test_filter_by_each_dimension(self):
        self.assertEqual(self.numbers("priority=urgent"), {self.leak.case_number})
        self.assertEqual(self.numbers(f"category={self.other_category.pk}"), {self.wifi.case_number})
        self.assertEqual(self.numbers(f"authority={self.maintenance.pk}"), {self.leak.case_number})
        self.assertEqual(self.numbers("status=submitted"), {self.idea.case_number})
        self.assertEqual(self.numbers("case_type=suggestion"), {self.idea.case_number})

    def test_filter_by_date(self):
        from datetime import timedelta

        from django.utils import timezone

        Case.objects.filter(pk=self.idea.pk).update(submitted_at=timezone.now() - timedelta(days=40))
        start = (timezone.localdate() - timedelta(days=7)).isoformat()
        self.assertEqual(self.numbers(f"date_from={start}"), {self.leak.case_number, self.wifi.case_number})

    def test_csv_export_respects_filters(self):
        response = self.client.get("/reports/?priority=urgent&export=csv")
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        body = response.content.decode("utf-8-sig")
        self.assertIn(self.leak.case_number, body)
        self.assertNotIn(self.wifi.case_number, body)

    def test_dashboard_filters_change_the_counts(self):
        counts = self.client.get("/dashboard/?priority=normal").context["counts"]
        self.assertEqual(counts["total"], 2)
