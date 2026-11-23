from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.mail import get_connection


class Command(BaseCommand):
    help = "Check SMTP connectivity without sending mail or printing secrets."

    def handle(self, *args, **options):
        if settings.EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend" or not settings.EMAIL_HOST:
            raise CommandError("SMTP delivery is unavailable: SMTP backend and host are not configured.")
        connection = get_connection(fail_silently=False)
        try:
            connection.open()
        except Exception as exc:
            # Do not echo transport exceptions: provider errors may contain account or host details.
            raise CommandError("SMTP connection failed; inspect the mail service configuration and safe server logs.") from None
        finally:
            try:
                connection.close()
            except Exception:
                pass
        self.stdout.write(self.style.SUCCESS(
            "SMTP server connection succeeded. No message was sent; mailbox delivery is not yet verified."
        ))
