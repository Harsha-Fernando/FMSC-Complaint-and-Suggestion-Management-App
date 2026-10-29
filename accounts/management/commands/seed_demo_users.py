"""Management command to seed demo authorities, categories, and test user accounts for all six roles."""
from django.core.management.base import BaseCommand
from accounts.models import User
from cases.models import Authority, Category

DEFAULT_PASSWORD = "Demo@pass2026"


class Command(BaseCommand):
    help = "Seed demo authorities, categories, and test user accounts for all 6 roles with predefined passwords."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=f"Password to assign to all demo accounts (default: {DEFAULT_PASSWORD})",
        )

    def handle(self, *args, **options):
        password = options["password"]

        # 1. Create or retrieve essential Authorities
        maint, _ = Authority.objects.get_or_create(
            name="Maintenance Division",
            defaults={"email": "maintenance@fmsc.example.lk", "is_active": True},
        )
        it_unit, _ = Authority.objects.get_or_create(
            name="IT Services Unit",
            defaults={"email": "itsupport@fmsc.example.lk", "is_active": True},
        )

        # 2. Create or retrieve essential Categories
        Category.objects.get_or_create(
            name="Facilities & Infrastructure",
            defaults={"is_active": True},
        )
        Category.objects.get_or_create(
            name="IT & Network Support",
            defaults={"is_active": True},
        )
        Category.objects.get_or_create(
            name="Academic & Faculty Services",
            defaults={"is_active": True},
        )
        Category.objects.get_or_create(
            name="Harassment",
            defaults={"description": "Reports regarding discrimination, misconduct, or harassment.", "is_active": True},
        )

        # 3. Seed one account per role
        accounts_data = [
            {
                "email": "student@test.example",
                "role": User.Role.STUDENT,
                "first_name": "Amaya",
                "last_name": "Perera",
                "registration_number": "FMSC/2024/0101",
                "cpm_number": "25678",
                "department": "Business Administration",
            },
            {
                "email": "lecturer@test.example",
                "role": User.Role.LECTURER,
                "first_name": "Dr. Saman",
                "last_name": "Kumara",
                "lecturer_id": "LEC-001",
                "department": "Accounting",
            },
            {
                "email": "admin@test.example",
                "role": User.Role.ADMIN,
                "first_name": "Nadeesha",
                "last_name": "Silva",
                "department": "Faculty Office",
            },
            {
                "email": "authority@test.example",
                "role": User.Role.AUTHORITY,
                "first_name": "Ruwan",
                "last_name": "Bandara",
                "authority": maint,
                "department": "Maintenance Division",
            },
            {
                "email": "management@test.example",
                "role": User.Role.MANAGEMENT,
                "first_name": "Prof. Chandana",
                "last_name": "Wickramasinghe",
                "department": "Dean's Office",
            },
            {
                "email": "sysadmin@test.example",
                "role": User.Role.SYSADMIN,
                "first_name": "System",
                "last_name": "Administrator",
                "department": "Faculty IT Operations",
                "is_staff": True,
                "is_superuser": True,
            },
        ]

        created = 0
        updated = 0

        for item in accounts_data:
            email = item["email"]
            user, is_new = User.objects.get_or_create(
                username=email,
                defaults={"email": email},
            )
            user.email = email
            user.role = item["role"]
            user.first_name = item.get("first_name", "")
            user.last_name = item.get("last_name", "")
            user.department = item.get("department", "")

            if "registration_number" in item:
                user.registration_number = item["registration_number"]
            if "cpm_number" in item:
                user.cpm_number = item["cpm_number"]
            if "lecturer_id" in item:
                user.lecturer_id = item["lecturer_id"]
            if "authority" in item:
                user.authority = item["authority"]
            if item.get("is_staff"):
                user.is_staff = True
            if item.get("is_superuser"):
                user.is_superuser = True

            user.set_password(password)
            user.needs_password_setup = False
            user.is_active = True
            user.save()

            if is_new:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully configured demo dataset:\n"
                f" - {created} user(s) created, {updated} user(s) updated\n"
                f" - Authorities: Maintenance Division, IT Services Unit\n"
                f" - Categories: Facilities & Infrastructure, IT & Network Support, Academic & Faculty Services\n"
                f" - Password for all demo accounts: {password}"
            )
        )
