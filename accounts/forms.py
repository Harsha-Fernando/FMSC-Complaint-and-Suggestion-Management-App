from django.utils.translation import gettext_lazy as gettext
from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from .models import User


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label=gettext("Email or registration number"),
        max_length=254,
        widget=forms.TextInput(attrs={"autocomplete": "username", "spellcheck": "false"}),
    )
    password = forms.CharField(
        label=gettext("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    error_messages = {
        "invalid_login": (
            gettext("That email, registration number or password is not right. "
            "Check them and try again.")
        ),
        "inactive": gettext("This account has been deactivated. Contact the faculty office."),
    }


class AccountCSVForm(forms.Form):
    csv_file = forms.FileField(label=gettext("CSV file"), help_text=gettext("Upload a UTF-8 CSV file, up to 5 MB and 10,000 accounts."), widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}))


class AccountPasswordResetForm(PasswordResetForm):
    """Imported accounts can set a password without enabling other unusable accounts."""
    def get_users(self, email):
        for user in User.objects.filter(email__iexact=email, is_active=True):
            if user.has_usable_password() or user.needs_password_setup:
                yield user
