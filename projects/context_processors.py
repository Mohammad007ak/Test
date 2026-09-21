from .nav import find_page_info, visible_nav_groups


def nav(request):
    if not request.user.is_authenticated:
        return {}
    url_name = request.resolver_match.url_name if request.resolver_match else None
    group_title, page_label = find_page_info(url_name) if url_name else (None, None)
    return {
        "nav_groups": visible_nav_groups(request.user),
        "breadcrumb_group": group_title,
        "breadcrumb_label": page_label,
    }
