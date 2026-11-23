from .models import UserPreferences


def user_preferences(request):
    if not request.user.is_authenticated:
        return {"user_preferences": None}
    preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
    return {"user_preferences": preferences}
