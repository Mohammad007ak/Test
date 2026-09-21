from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

ROLE_EXECUTOR = settings.GROUP_EXECUTOR
ROLE_PROJECT_CONTROL = settings.GROUP_PROJECT_CONTROL
ROLE_DATA_ENTRY = settings.GROUP_DATA_ENTRY
ROLE_SUPER_ADMIN = settings.GROUP_SUPER_ADMIN

ALL_ROLES = (ROLE_EXECUTOR, ROLE_PROJECT_CONTROL, ROLE_DATA_ENTRY, ROLE_SUPER_ADMIN)


def user_roles(user):
    if not user.is_authenticated:
        return set()
    if user.is_superuser:
        return set(ALL_ROLES)
    return set(user.groups.values_list("name", flat=True))


def role_required(*allowed_roles):
    """محدود کردن دسترسی یک گزارش/نما به نقش‌های مجاز طبق سند نیازمندی‌ها."""

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if request.user.is_superuser or user_roles(request.user) & set(allowed_roles):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("شما مجوز مشاهده‌ی این گزارش را ندارید.")

        return _wrapped

    return decorator
