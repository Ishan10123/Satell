from django.conf import settings
from django.db import models


class UserPreferences(models.Model):
    class Theme(models.TextChoices):
        SYSTEM = "system", "System"
        LIGHT = "light", "Light"
        DARK = "dark", "Dark"

    class MessageSpacing(models.TextChoices):
        COMFORTABLE = "comfortable", "Comfortable"
        COMPACT = "compact", "Compact"

    class ResponseStyle(models.TextChoices):
        NATURAL = "natural", "Natural"
        CONCISE = "concise", "Concise"
        DETAILED = "detailed", "Detailed"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="satell_preferences")
    display_name = models.CharField(max_length=80, blank=True)
    theme = models.CharField(max_length=8, choices=Theme.choices, default=Theme.SYSTEM)
    message_spacing = models.CharField(max_length=12, choices=MessageSpacing.choices,
                                       default=MessageSpacing.COMFORTABLE)
    response_style = models.CharField(max_length=12, choices=ResponseStyle.choices,
                                      default=ResponseStyle.NATURAL)
    show_code_blocks = models.BooleanField(default=True)
    show_source_cards = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for user {self.user_id}"


class CreatorProfile(models.Model):
    """Site-owned trusted profile metadata; public fields are explicitly toggled."""

    class VerificationStatus(models.TextChoices):
        OWNER_SUPPLIED_UNVERIFIED = "owner_supplied_unverified", "Supplied by owner; not independently verified"
        OWNER_CONFIRMED = "owner_confirmed", "Confirmed by owner"
        INDEPENDENTLY_REVIEWED = "independently_reviewed", "Independently reviewed"

    key = models.CharField(max_length=32, primary_key=True, default="satell", editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="owned_creator_profiles")
    full_name = models.CharField(max_length=160)
    headline = models.CharField(max_length=240, blank=True)
    biography = models.TextField(blank=True)
    education = models.TextField(blank=True)
    current_role = models.CharField(max_length=240, blank=True)
    experience = models.TextField(blank=True)
    skills = models.TextField(blank=True)
    projects = models.TextField(blank=True)
    verification_status = models.CharField(max_length=32, choices=VerificationStatus.choices,
                                           default=VerificationStatus.OWNER_SUPPLIED_UNVERIFIED)
    linkedin_url = models.URLField(max_length=300, blank=True)
    github_url = models.URLField(max_length=300, blank=True)
    leetcode_url = models.URLField(max_length=300, blank=True)
    hackerrank_url = models.URLField(max_length=300, blank=True)
    portfolio_url = models.URLField(max_length=300, blank=True)
    profile_is_public = models.BooleanField(default=True)
    name_is_public = models.BooleanField(default=True)
    headline_is_public = models.BooleanField(default=False)
    biography_is_public = models.BooleanField(default=False)
    education_is_public = models.BooleanField(default=False)
    current_role_is_public = models.BooleanField(default=False)
    experience_is_public = models.BooleanField(default=False)
    skills_is_public = models.BooleanField(default=False)
    projects_is_public = models.BooleanField(default=False)
    linkedin_is_public = models.BooleanField(default=True)
    github_is_public = models.BooleanField(default=True)
    leetcode_is_public = models.BooleanField(default=True)
    hackerrank_is_public = models.BooleanField(default=True)
    portfolio_is_public = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Satell creator profile"

    def __str__(self):
        return self.full_name
