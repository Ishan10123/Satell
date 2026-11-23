from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth import get_user_model
from django import forms

from .models import CreatorProfile, UserPreferences


class AccountIdentifierResetForm(forms.Form):
    identifier = forms.CharField(max_length=254, strip=True, label="Username or email")

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

    def send_reset(self, *, domain: str, protocol: str, from_email: str | None,
                   html_email_template_name: str, timeout_seconds: int) -> None:
        identifier = self.cleaned_data["identifier"].strip()
        User = get_user_model()
        exact_username = list(User._default_manager.filter(username=identifier, is_active=True)[:2])
        username_matches = exact_username or list(
            User._default_manager.filter(username__iexact=identifier, is_active=True)[:2]
        )
        if username_matches:
            users = username_matches if len(username_matches) == 1 else []
        else:
            email_matches = list(User._default_manager.filter(email__iexact=identifier, is_active=True)[:2])
            # If a mailbox belongs to multiple accounts, fail closed rather than
            # generating multiple reset links from one ambiguous identifier.
            users = email_matches if len(email_matches) == 1 else []
        valid_emails = {user.email.casefold() for user in users if user.email and user.has_usable_password()}
        for email in valid_emails:
            form = PasswordResetForm({"email": email})
            if form.is_valid():
                form.save(
                    request=self.request,
                    domain_override=domain,
                    use_https=protocol == "https",
                    from_email=from_email,
                    subject_template_name="accounts/password_reset_subject.txt",
                    email_template_name="accounts/password_reset_email.txt",
                    html_email_template_name=html_email_template_name,
                    extra_email_context={"expiration_hours": max(1, (timeout_seconds + 3599) // 3600)},
                )


class AccountProfileForm(forms.ModelForm):
    class Meta:
        model = UserPreferences
        fields = ("display_name",)


class PreferencesForm(forms.ModelForm):
    class Meta:
        model = UserPreferences
        fields = ("theme", "message_spacing", "response_style", "show_code_blocks", "show_source_cards")
        widgets = {"show_code_blocks": forms.CheckboxInput(), "show_source_cards": forms.CheckboxInput()}


class CreatorVisibilityForm(forms.ModelForm):
    class Meta:
        model = CreatorProfile
        fields = ("profile_is_public", "name_is_public", "headline_is_public", "biography_is_public",
                  "education_is_public", "current_role_is_public", "experience_is_public",
                  "skills_is_public", "projects_is_public",
                  "linkedin_is_public", "github_is_public", "leetcode_is_public",
                  "hackerrank_is_public", "portfolio_is_public")


class CreatorProfileForm(forms.ModelForm):
    class Meta:
        model = CreatorProfile
        fields = ("full_name", "headline", "biography", "education", "current_role",
                  "experience", "skills", "projects", "linkedin_url", "github_url",
                  "leetcode_url", "hackerrank_url", "portfolio_url")
        widgets = {
            "biography": forms.Textarea(attrs={"rows": 3}),
            "education": forms.Textarea(attrs={"rows": 3}),
            "experience": forms.Textarea(attrs={"rows": 4}),
            "skills": forms.Textarea(attrs={"rows": 3}),
            "projects": forms.Textarea(attrs={"rows": 3}),
        }

    _allowed_profile_hosts = {
        "linkedin_url": {"www.linkedin.com"},
        "github_url": {"github.com"},
        "leetcode_url": {"leetcode.com"},
        "hackerrank_url": {"www.hackerrank.com"},
        "portfolio_url": {"portfolio-three-mauve-72.vercel.app"},
    }

    def clean(self):
        cleaned = super().clean()
        from urllib.parse import urlsplit

        for field, allowed_hosts in self._allowed_profile_hosts.items():
            value = cleaned.get(field)
            if not value:
                continue
            parsed = urlsplit(value)
            if (parsed.scheme != "https" or parsed.hostname not in allowed_hosts
                    or parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment):
                self.add_error(field, "Use the verified HTTPS profile URL for this service.")
        return cleaned
