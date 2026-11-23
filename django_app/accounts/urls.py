from django.contrib.auth import views as auth_views
from django.urls import path
from django.urls import reverse_lazy

from . import views


app_name = "accounts"
urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("password-reset/", views.password_reset_request, name="password_reset"),
    path("password-reset/sent/", views.password_reset_sent, name="password_reset_sent"),
    path("password-reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html",
        success_url=reverse_lazy("accounts:password_reset_complete")), name="password_reset_confirm"),
    path("password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html"), name="password_reset_complete"),
    path("profile/", views.profile, name="profile"),
    path("profile/creator-visibility/", views.creator_visibility, name="creator_visibility"),
    path("personalization/", views.personalization, name="personalization"),
    path("settings/", views.settings_page, name="settings"),
    path("about/", views.about, name="about"),
    path("password-change/", auth_views.PasswordChangeView.as_view(
        template_name="accounts/password_change.html",
        success_url=reverse_lazy("accounts:settings")), name="password_change"),
]
