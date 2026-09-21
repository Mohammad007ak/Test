from .nav import visible_nav_groups


def nav(request):
    if not request.user.is_authenticated:
        return {}
    return {"nav_groups": visible_nav_groups(request.user)}
