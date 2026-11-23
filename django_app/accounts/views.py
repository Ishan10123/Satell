from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.cache import cache
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from urllib.parse import urlsplit
import hashlib
import logging

from .forms import (AccountIdentifierResetForm, AccountProfileForm, CreatorProfileForm,
                    CreatorVisibilityForm, PreferencesForm)
from .models import CreatorProfile, UserPreferences
from django.views.decorators.http import require_POST


@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect("accounts:login")


logger = logging.getLogger(__name__)


def _reset_request_allowed(request) -> bool:
    address = request.META.get("REMOTE_ADDR", "unknown")
    key = "satell:password-reset:" + hashlib.sha256(address.encode("utf-8")).hexdigest()
    try:
        if cache.add(key, 1, settings.PASSWORD_RESET_RATE_WINDOW_SECONDS):
            return True
        return cache.incr(key) <= settings.PASSWORD_RESET_RATE_LIMIT
    except Exception:
        logger.error("Password reset throttling unavailable; request rejected.")
        return False


@require_http_methods(["GET", "POST"])
def password_reset_request(request):
    form = AccountIdentifierResetForm(request.POST or None, request=request)
    if request.method == "POST":
        if form.is_valid():
            if _reset_request_allowed(request):
                parsed = urlsplit(settings.PUBLIC_APP_BASE_URL)
                domain = parsed.netloc
                try:
                    console_backend = (settings.DEBUG and settings.EMAIL_BACKEND ==
                        "django.core.mail.backends.console.EmailBackend")
                    if not settings.EMAIL_HOST and not console_backend:
                        raise RuntimeError("SMTP host is not configured")
                    form.send_reset(domain=domain, protocol=parsed.scheme,
                                    from_email=settings.DEFAULT_FROM_EMAIL,
                                    html_email_template_name="accounts/password_reset_email.html",
                                    timeout_seconds=settings.PASSWORD_RESET_TIMEOUT)
                except Exception:
                    # No submitted identifier, email address, token, or credential is logged.
                    logger.error("Password reset email delivery failed; inspect SMTP configuration.")
                    if request.user.is_authenticated and request.user.is_staff:
                        from django.contrib import messages
                        messages.error(request, "Password reset email is not configured correctly. Ask an administrator to check SMTP settings.")
            return redirect("accounts:password_reset_sent")
    return render(request, "accounts/password_reset_form.html", {"form": form})


def password_reset_sent(request):
    return render(request, "accounts/password_reset_sent.html")


def _preferences_for(user):
    preferences, _ = UserPreferences.objects.get_or_create(user=user)
    return preferences


def public_creator_fields(profile):
    if not profile or not profile.profile_is_public:
        return None
    fields = {"name": profile.full_name if profile.name_is_public else "",
              "headline": profile.headline if profile.headline_is_public else "",
              "biography": profile.biography if profile.biography_is_public else "",
              "education": profile.education if profile.education_is_public else "",
              "current_role": profile.current_role if profile.current_role_is_public else "",
              "experience": profile.experience if profile.experience_is_public else "",
              "skills": profile.skills if profile.skills_is_public else "",
              "projects": profile.projects if profile.projects_is_public else "",
              "verification_status": profile.get_verification_status_display()}
    fields["owner_supplied_details_public"] = any(fields[key] for key in (
        "headline", "biography", "education", "current_role", "experience", "skills", "projects"))
    candidates = (
        ("LinkedIn", "linkedin", profile.linkedin_url, profile.linkedin_is_public,
         "https", "www.linkedin.com"),
        ("GitHub", "github", profile.github_url, profile.github_is_public,
         "https", "github.com"),
        ("LeetCode", "leetcode", profile.leetcode_url, profile.leetcode_is_public,
         "https", "leetcode.com"),
        ("HackerRank", "hackerrank", profile.hackerrank_url, profile.hackerrank_is_public,
         "https", "www.hackerrank.com"),
        ("Portfolio", "portfolio", profile.portfolio_url, profile.portfolio_is_public,
         "https", "portfolio-three-mauve-72.vercel.app"),
    )
    links = []
    for label, key, value, enabled, scheme, host in candidates:
        parsed = urlsplit(value or "")
        if enabled and parsed.scheme == scheme and parsed.hostname == host and not parsed.username and not parsed.password:
            links.append({"label": label, "key": key, "url": value, "icon": label[:2].upper()})
    fields["links"] = links
    return fields


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    preferences = _preferences_for(request.user)
    form = AccountProfileForm(request.POST or None, instance=preferences)
    creator = CreatorProfile.objects.filter(key="satell", owner=request.user).first()
    creator_form = CreatorProfileForm(request.POST or None, instance=creator) if creator else None
    if request.method == "POST" and "save_creator_profile" in request.POST:
        if creator is None:
            raise Http404
        if creator_form and creator_form.is_valid():
            creator_form.save()
            from django.contrib import messages
            messages.success(request, "Your professional profile was updated.")
            return redirect("accounts:profile")
    elif request.method == "POST" and form.is_valid():
        form.save()
        from django.contrib import messages
        messages.success(request, "Your account profile was updated.")
        return redirect("accounts:profile")
    visibility_form = CreatorVisibilityForm(instance=creator) if creator else None
    return render(request, "accounts/profile.html", {
        "form": form, "creator": creator,
        "creator_profile_form": creator_form,
        "creator_visibility_form": visibility_form,
        "public_profile": public_creator_fields(creator),
    })


@login_required
@require_http_methods(["GET", "POST"])
def creator_visibility(request):
    creator = get_object_or_404(CreatorProfile, key="satell", owner=request.user)
    form = CreatorVisibilityForm(request.POST or None, instance=creator)
    if request.method == "POST" and form.is_valid():
        form.save()
        from django.contrib import messages
        messages.success(request, "Public creator-profile visibility was updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/creator_visibility.html", {"form": form})


def creator_public(request):
    creator = CreatorProfile.objects.filter(key="satell").first()
    public_profile = public_creator_fields(creator)
    return render(request, "accounts/creator_public.html", {"public_profile": public_profile})


@login_required
@require_http_methods(["GET", "POST"])
def personalization(request):
    preferences = _preferences_for(request.user)
    form = PreferencesForm(request.POST or None, instance=preferences)
    if request.method == "POST" and form.is_valid():
        form.save()
        from django.contrib import messages
        messages.success(request, "Your personalization settings were saved.")
        return redirect("accounts:personalization")
    return render(request, "accounts/personalization.html", {"form": form})


@login_required
@require_http_methods(["GET"])
def settings_page(request):
    return render(request, "accounts/settings.html", {
        "account_user": request.user,
        "email_delivery_configured": bool(settings.EMAIL_HOST and settings.DEFAULT_FROM_EMAIL),
    })


def about(request):
    return render(request, "accounts/about.html")
