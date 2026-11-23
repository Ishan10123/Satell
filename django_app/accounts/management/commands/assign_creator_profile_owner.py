from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounts.models import CreatorProfile


class Command(BaseCommand):
    help = "Bind the Satell creator-profile editor to an explicitly selected account."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)

    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username=options["username"], is_active=True).first()
        if user is None:
            raise CommandError("No active account matches that username.")
        profile, _ = CreatorProfile.objects.get_or_create(key="satell", defaults={"full_name": "Ishan Kaushik"})
        if profile.owner_id and profile.owner_id != user.pk:
            raise CommandError("A creator-profile owner is already assigned; contact an administrator to review reassignment.")
        profile.owner = user
        profile.save(update_fields=("owner", "updated_at"))
        self.stdout.write(self.style.SUCCESS("Creator-profile editing is assigned to the selected account."))
