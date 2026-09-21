from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "ایجاد گروه‌های نقش سیستم (مجری، کنترل پروژه، مسئول ورود داده، ادمین کل سامانه)."

    def handle(self, *args, **options):
        role_names = [
            settings.GROUP_EXECUTOR,
            settings.GROUP_PROJECT_CONTROL,
            settings.GROUP_DATA_ENTRY,
            settings.GROUP_SUPER_ADMIN,
        ]
        for name in role_names:
            group, created = Group.objects.get_or_create(name=name)
            status = "ایجاد شد" if created else "از قبل موجود بود"
            self.stdout.write(self.style.SUCCESS(f"گروه «{name}» {status}."))
