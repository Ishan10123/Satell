import re
import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from pathlib import Path
from django.core.management import call_command, CommandError
from io import StringIO

from .models import CreatorProfile, UserPreferences


class PasswordRecoveryTests(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.user = get_user_model().objects.create_user(
            username="recovery-user", email="recovery@example.test", password="Existing-good-pass-981!"
        )

    def post_identifier(self, identifier):
        return self.client.post(reverse("accounts:password_reset"), {"identifier": identifier})

    def confirmation_url(self):
        body = mail.outbox[-1].body
        match = re.search(r"https?://[^\s]+/accounts/password-reset/([^\s]+)", body)
        self.assertIsNotNone(match)
        return "/accounts/password-reset/" + match.group(1)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", EMAIL_HOST="smtp.example.test")
    def test_username_reset_sends_link_only_to_registered_email(self):
        response = self.post_identifier("recovery-user")
        self.assertRedirects(response, reverse("accounts:password_reset_sent"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["recovery@example.test"])
        self.assertIn("one-time link", mail.outbox[0].body)
        self.assertNotIn("Existing-good-pass-981!", mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", EMAIL_HOST="smtp.example.test")
    def test_email_reset_sends_to_registered_email(self):
        self.post_identifier("RECOVERY@example.test")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["recovery@example.test"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", EMAIL_HOST="smtp.example.test")
    def test_ambiguous_email_does_not_send_reset_links_to_multiple_accounts(self):
        get_user_model().objects.create_user(
            username="recovery-second", email="recovery@example.test", password="Second-good-pass-983!"
        )
        response = self.post_identifier("recovery@example.test")
        self.assertRedirects(response, reverse("accounts:password_reset_sent"))
        self.assertEqual(mail.outbox, [])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", EMAIL_HOST="smtp.example.test")
    def test_exact_username_wins_over_case_variant_username(self):
        get_user_model().objects.create_user(
            username="Recovery-User", email="other-recovery@example.test", password="Other-good-pass-984!"
        )
        self.post_identifier("recovery-user")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["recovery@example.test"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", EMAIL_HOST="smtp.example.test")
    def test_unknown_username_and_email_return_same_public_confirmation(self):
        username_response = self.post_identifier("unknown-user")
        self.client.get(username_response.url)
        username_body = re.sub(rb'value="[^"]+"', b'value="<token>"', self.client.get(reverse("accounts:password_reset_sent")).content)
        email_response = self.post_identifier("nobody@example.test")
        self.client.get(email_response.url)
        email_body = re.sub(rb'value="[^"]+"', b'value="<token>"', self.client.get(reverse("accounts:password_reset_sent")).content)
        self.assertEqual(username_body, email_body)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", EMAIL_HOST="smtp.example.test")
    def test_valid_reset_changes_password_and_token_cannot_be_reused(self):
        self.post_identifier("recovery-user")
        url = self.confirmation_url()
        first_get = self.client.get(url, follow=True)
        self.assertEqual(first_get.status_code, 200)
        reset_url = first_get.request["PATH_INFO"]
        response = self.client.post(reset_url, {"new_password1": "New-good-pass-482!", "new_password2": "New-good-pass-482!"})
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("New-good-pass-482!"))
        reused = self.client.get(url, follow=True)
        self.assertEqual(reused.status_code, 200)
        self.assertContains(reused, "invalid, expired, or has already been used")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", EMAIL_HOST="smtp.example.test",
                       PASSWORD_RESET_TIMEOUT=0)
    def test_expired_token_is_rejected(self):
        self.post_identifier("recovery-user")
        # Django's token age is measured in seconds; allow the zero-second
        # boundary to pass deterministically before following the emailed URL.
        time.sleep(1.05)
        response = self.client.get(self.confirmation_url(), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "invalid, expired, or has already been used")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", EMAIL_HOST="smtp.example.test",
                       PASSWORD_RESET_RATE_LIMIT=1, PASSWORD_RESET_RATE_WINDOW_SECONDS=3600)
    def test_request_rate_limit_is_shared_for_known_and_unknown_accounts(self):
        first = self.post_identifier("recovery-user")
        second = self.post_identifier("unknown-user")
        self.assertEqual(first.status_code, second.status_code)
        self.assertEqual(first.url, second.url)
        self.assertEqual(len(mail.outbox), 1)

    def test_csrf_is_required_for_reset_request(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("accounts:password_reset"), {"identifier": "recovery-user"})
        self.assertEqual(response.status_code, 403)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST="")
    def test_missing_smtp_uses_same_public_confirmation_without_fake_delivery(self):
        response = self.post_identifier("recovery-user")
        self.assertRedirects(response, reverse("accounts:password_reset_sent"))
        self.assertEqual(mail.outbox, [])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", EMAIL_HOST="smtp.example.test")
    @patch("accounts.forms.AccountIdentifierResetForm.send_reset", side_effect=RuntimeError("provider password leaked"))
    def test_smtp_failure_keeps_generic_public_response_and_safe_log(self, _send):
        with self.assertLogs("accounts.views", level="ERROR") as captured:
            response = self.post_identifier("recovery-user")
        self.assertRedirects(response, reverse("accounts:password_reset_sent"))
        self.assertNotIn("provider password leaked", "\n".join(captured.output))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST="")
    def test_smtp_diagnostic_reports_unavailable_without_secrets(self):
        output = StringIO()
        with self.assertRaises(CommandError) as caught:
            call_command("check_smtp", stdout=output)
        self.assertIn("SMTP delivery is unavailable", str(caught.exception))
        self.assertNotIn("password", str(caught.exception).casefold())

    def test_login_has_keyboard_accessible_password_visibility_control(self):
        response = self.client.get(reverse("accounts:login"))
        html = response.content.decode()
        self.assertRegex(html, r'<input[^>]+type="password"')
        self.assertContains(response, 'aria-label="Show password"')
        self.assertContains(response, "Forgot password?")
        script = open("chat/static/chat/app.js", encoding="utf-8").read()
        self.assertIn('field.type = visible ? "text" : "password"', script)
        self.assertIn('button.setAttribute("aria-label", visible ? "Hide password" : "Show password")', script)


class ProfileAndPersonalizationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="profile-owner", email="owner@example.test",
                                              password="Owner-good-pass-981!")
        self.other = User.objects.create_user(username="profile-other", email="other@example.test",
                                              password="Other-good-pass-982!")

    def test_public_creator_profile_has_only_the_verified_links(self):
        response = self.client.get(reverse("creator_public"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ishan Kaushik")
        expected = (
            "https://www.linkedin.com/in/ishankaushik/",
            "https://github.com/Ishan10123",
            "https://leetcode.com/u/Ishan_2003/",
            "https://www.hackerrank.com/profile/ishurbt1",
            "https://portfolio-three-mauve-72.vercel.app/",
        )
        html = response.content.decode()
        for url in expected:
            self.assertIn(f'href="{url}"', html)
        self.assertEqual(html.count('target="_blank" rel="noopener noreferrer"'), 5)
        self.assertNotIn("instagram.com", html.casefold())
        self.assertNotIn("phone", html.casefold())

    def test_private_profile_requires_authentication_and_is_user_scoped(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.owner)
        profile = self.client.get(reverse("accounts:profile"))
        self.assertEqual(profile.status_code, 200)
        self.assertContains(profile, "owner@example.test")
        self.assertNotContains(profile, "other@example.test")

    def test_settings_page_renders_public_creator_link(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("accounts:settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("creator_public"))

    def test_creator_visibility_edit_requires_the_assigned_owner(self):
        creator = CreatorProfile.objects.get(key="satell")
        creator.owner = self.owner
        creator.save(update_fields=("owner", "updated_at"))
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("accounts:creator_visibility"),
            {"profile_is_public": "on", "name_is_public": "on"}).status_code, 404)
        self.client.force_login(self.owner)
        response = self.client.post(reverse("accounts:creator_visibility"), {
            "profile_is_public": "on", "name_is_public": "on", "linkedin_is_public": "on",
            "leetcode_is_public": "on", "hackerrank_is_public": "on", "portfolio_is_public": "on",
        })
        self.assertEqual(response.status_code, 302)
        creator.refresh_from_db()
        self.assertFalse(creator.github_is_public)
        public = self.client.get(reverse("creator_public"))
        self.assertNotContains(public, "https://github.com/Ishan10123")

    def test_creator_profile_edit_is_owner_scoped_and_urls_are_restricted(self):
        creator = CreatorProfile.objects.get(key="satell")
        creator.owner = self.owner
        creator.save(update_fields=("owner", "updated_at"))
        data = {
            "save_creator_profile": "1", "full_name": "Ishan Kaushik",
            "headline": "AI Engineer · Software Engineer", "biography": "Owner supplied summary.",
            "education": "Owner supplied education.", "current_role": "Software Engineer at vTech Solution Inc.",
            "experience": "Python backend and RAG work.", "skills": "Python; Django; RAG.",
            "projects": "Satell; Proposal Bot.",
            "linkedin_url": "https://www.linkedin.com/in/ishankaushik/",
            "github_url": "https://github.com/Ishan10123",
            "leetcode_url": "https://leetcode.com/u/Ishan_2003/",
            "hackerrank_url": "https://www.hackerrank.com/profile/ishurbt1",
            "portfolio_url": "https://portfolio-three-mauve-72.vercel.app/",
        }
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("accounts:profile"), data).status_code, 404)
        self.client.force_login(self.owner)
        bad_url = {**data, "github_url": "javascript:alert(1)"}
        self.assertEqual(self.client.post(reverse("accounts:profile"), bad_url).status_code, 200)
        self.assertNotEqual(CreatorProfile.objects.get(key="satell").headline, data["headline"])
        response = self.client.post(reverse("accounts:profile"), data)
        self.assertEqual(response.status_code, 302)
        creator.refresh_from_db()
        self.assertEqual(creator.current_role, data["current_role"])
        self.assertEqual(creator.verification_status, CreatorProfile.VerificationStatus.OWNER_SUPPLIED_UNVERIFIED)

    def test_new_profile_fields_stay_private_until_owner_enables_them(self):
        creator = CreatorProfile.objects.get(key="satell")
        self.assertEqual(creator.verification_status, CreatorProfile.VerificationStatus.OWNER_SUPPLIED_UNVERIFIED)
        response = self.client.get(reverse("creator_public"))
        self.assertNotContains(response, "Rajasthan Technical University")
        self.assertNotContains(response, "vTech Solution Inc.")
        creator.education_is_public = True
        creator.current_role_is_public = True
        creator.save(update_fields=("education_is_public", "current_role_is_public", "updated_at"))
        response = self.client.get(reverse("creator_public"))
        self.assertContains(response, "Rajasthan Technical University")
        self.assertContains(response, "vTech Solution Inc.")
        self.assertContains(response, "not independently verified")

    def test_personalization_is_persisted_per_user_and_theme_is_server_rendered(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("accounts:personalization"), {
            "theme": "dark", "message_spacing": "compact", "response_style": "concise",
            "show_code_blocks": "on",
        })
        self.assertEqual(response.status_code, 302)
        preferences = UserPreferences.objects.get(user=self.owner)
        self.assertEqual((preferences.theme, preferences.message_spacing, preferences.response_style),
                         ("dark", "compact", "concise"))
        self.assertFalse(preferences.show_source_cards)
        workspace = self.client.get(reverse("conversations:list"))
        self.assertContains(workspace, 'data-theme="dark"')
        self.assertEqual(UserPreferences.objects.filter(user=self.other).count(), 0)

    def test_account_menu_is_aria_enabled_and_has_no_upgrade_entry(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("conversations:list"))
        self.assertContains(response, 'aria-haspopup="menu"')
        self.assertContains(response, "Personalization")
        self.assertContains(response, "About Satell")
        self.assertNotContains(response, "Upgrade Plan")
        script = (Path(__file__).resolve().parents[1] / "chat" / "static" / "chat" / "app.js").read_text()
        self.assertIn('event.key === "Escape" && activeDropdown', script)
        self.assertIn("document.body.append(panel)", script)
        self.assertIn("ArrowDown", script)

    def test_display_name_edit_changes_only_the_authenticated_users_preferences(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("accounts:profile"), {"display_name": "Ishan"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(UserPreferences.objects.get(user=self.owner).display_name, "Ishan")
        self.assertEqual(UserPreferences.objects.filter(user=self.other).count(), 0)
