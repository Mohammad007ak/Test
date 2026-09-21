import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """ساخت خودکار کاربر ادمین از روی متغیرهای محیطی، در صورت نبود آن.

    برخی پلتفرم‌های PaaS (مثل Darkube) دسترسی ترمینال تعاملی ساده در اختیار
    نمی‌گذارند، پس دستور استاندارد ``createsuperuser`` قابل اجرا نیست. این
    دستور در ``entrypoint.sh`` روی هر استارت اجرا می‌شود و بی‌ضرر (no-op) است
    مگر این سه متغیر محیطی تنظیم شده باشند:
    DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, DJANGO_SUPERUSER_PASSWORD
    """

    help = "در صورت تنظیم متغیرهای محیطی DJANGO_SUPERUSER_*، یک کاربر ادمین می‌سازد."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not username or not password:
            self.stdout.write("DJANGO_SUPERUSER_USERNAME/PASSWORD تنظیم نشده؛ رد شد.")
            return

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"کاربر «{username}» از قبل وجود دارد؛ کاری انجام نشد.")
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"کاربر ادمین «{username}» ساخته شد."))
