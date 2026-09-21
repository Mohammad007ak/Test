"""فهرست ثابت گزارش‌ها به تفکیک گروه، به همراه نقش‌های مجاز هر گزارش.

این ماژول هم توسط ``views.report_home`` و هم توسط ``context_processors.nav``
استفاده می‌شود تا فهرست گزارش‌ها فقط یک‌بار تعریف شود.
"""

from .permissions import ROLE_EXECUTOR, ROLE_PROJECT_CONTROL, ROLE_SUPER_ADMIN

NAV_GROUPS = [
    ("گزارش‌های پروژه", [
        ("project_status_overview", "وضعیت کلی پروژه‌ها", {ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL}),
        ("project_progress", "پیشرفت پروژه‌ها", {ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL, ROLE_EXECUTOR}),
        ("delayed_projects", "پروژه‌های دارای تأخیر", {ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL}),
    ]),
    ("فرآیند تصویب", [
        ("proposals_in_progress", "پروپوزال‌های در جریان", {ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL}),
        ("approval_rate", "نرخ تصویب", {ROLE_SUPER_ADMIN}),
        ("average_approval_time", "میانگین زمان تصویب", {ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL}),
    ]),
    ("نیروی انسانی", [
        ("workforce_composition", "ترکیب نیروها", {ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL}),
        ("workload_report", "بار کاری افراد", {ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL}),
        ("free_capacity", "ظرفیت آزاد", {ROLE_SUPER_ADMIN, ROLE_EXECUTOR}),
        ("soldier_service_end", "پایان خدمت سربازان", {ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL, ROLE_EXECUTOR}),
        ("external_contracts", "قراردادهای همکاران خارجی", {ROLE_SUPER_ADMIN}),
    ]),
    ("مجریان", [
        ("executor_performance", "عملکرد مجریان", {ROLE_SUPER_ADMIN}),
        ("executor_dashboard", "داشبورد مجری", {ROLE_SUPER_ADMIN, ROLE_EXECUTOR}),
    ]),
]


def visible_nav_groups(user):
    from .permissions import user_roles

    roles = user_roles(user)
    groups = []
    for title, items in NAV_GROUPS:
        visible = [(url, label) for url, label, allowed in items if user.is_superuser or roles & allowed]
        if visible:
            groups.append((title, visible))
    return groups


# صفحاتی که در NAV_GROUPS نیستند (چون به یک شناسه‌ی پروژه نیاز دارند) ولی
# باید برای مسیر نان (breadcrumb) به یک گروه نسبت داده شوند.
_EXTRA_PAGE_INFO = {
    "project_profile": ("گزارش‌های پروژه", "شناسنامه‌ی پروژه"),
}


def find_page_info(url_name):
    """گروه و عنوان فارسی یک صفحه را برای نمایش در مسیر ناوبری برمی‌گرداند."""
    if url_name in _EXTRA_PAGE_INFO:
        return _EXTRA_PAGE_INFO[url_name]
    for group_title, items in NAV_GROUPS:
        for name, label, _allowed in items:
            if name == url_name:
                return group_title, label
    return None, None
