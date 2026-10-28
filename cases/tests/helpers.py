import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from accounts.models import User
from cases.models import Authority, Category

PASSWORD = "Test@pass-2026"
_MEDIA = tempfile.mkdtemp(prefix="fmsc-test-media-")


def jpeg(name="photo.jpg", size=(40, 30)):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 120, 80)).save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


def mp4(name="clip.mp4", extra_bytes=2048):
    header = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    return SimpleUploadedFile(name, header + b"\x00" * extra_bytes, content_type="video/mp4")


@override_settings(
    MEDIA_ROOT=_MEDIA,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    NOTIFY_BY_EMAIL=True,
)
class CaseTestCase(TestCase):
    """Creates one user per role plus a small authority list and categories."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.maintenance = Authority.objects.create(name="Maintenance Division", email="works@example.edu")
        cls.it_unit = Authority.objects.create(name="IT Unit", email="it@example.edu")
        cls.category = Category.objects.create(name="Maintenance")
        cls.other_category = Category.objects.create(name="IT systems")

        def make(email, role, **extra):
            user = User.objects.create(email=email, username=email, role=role, first_name=email.split("@")[0],
                                       **extra)
            user.set_password(PASSWORD)
            user.save()
            return user

        cls.student = make("student@example.edu", User.Role.STUDENT, registration_number="FMSC/2024/0001")
        cls.other_student = make("other@example.edu", User.Role.STUDENT)
        cls.lecturer = make("lecturer@example.edu", User.Role.LECTURER)
        cls.admin = make("admin@example.edu", User.Role.ADMIN)
        cls.officer = make("officer@example.edu", User.Role.AUTHORITY, authority=cls.maintenance)
        cls.it_officer = make("itofficer@example.edu", User.Role.AUTHORITY, authority=cls.it_unit)
        cls.manager = make("manager@example.edu", User.Role.MANAGEMENT)

    def login(self, user):
        self.client.logout()
        self.assertTrue(self.client.login(username=user.email, password=PASSWORD))

    def submit(self, user=None, **overrides):
        """Submit a case through the real form and return it."""
        from cases.models import Case

        self.login(user or self.student)
        data = {
            "case_type": "complaint",
            "priority": "urgent",
            "category": self.category.pk,
            "location": "Block B corridor",
            "title": "Water leak near corridor",
            "description": "Water dripping from the ceiling.",
            "declaration": "on",
        }
        data.update(overrides)
        response = self.client.post("/cases/new/", data)
        self.assertEqual(response.status_code, 302, getattr(response, "context", None)
                         and response.context["form"].errors)
        return Case.objects.latest("pk")

    def assign(self, case, authority=None, note=""):
        self.login(self.admin)
        response = self.client.post(
            f"/cases/{case.case_number}/review/",
            {"action": "assign", "category": case.category_id, "priority": case.priority,
             "authority": (authority or self.maintenance).pk, "internal_note": note},
        )
        self.assertEqual(response.status_code, 302)
        case.refresh_from_db()
        return case

    def progress(self, case, user=None, **data):
        self.login(user or self.officer)
        payload = {"new_status": "in_progress", "comment": "", "resolution_note": ""}
        payload.update(data)
        return self.client.post(f"/cases/{case.case_number}/progress/", payload)
