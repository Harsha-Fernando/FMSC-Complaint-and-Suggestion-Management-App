"""Small local SVG icon set. No remote scripts, fonts, or icon requests."""
from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()
PATHS = {
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a20 20 0 0 1 0 18 20 20 0 0 1 0-18Z"/>',
    "megaphone": '<path d="m4 10 12-5v14L4 14v-4Zm0 0H2v4h2m3 1 1 6h3l-1-5M20 8l2-1m-2 5h3m-3 4 2 1"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 3"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="m7 12 3 3 7-7"/>',
    "alert": '<circle cx="12" cy="12" r="9"/><path d="M12 7v6m0 4h.01"/>',
    "trend": '<path d="m3 17 6-6 4 3 8-10m-6 0h6v6"/>',
    "list": '<path d="M8 5h13M8 12h13M8 19h13M3 5h.01M3 12h.01M3 19h.01"/>',
    "edit": '<path d="m15 4 5 5M4 20l1-6L16 3a2 2 0 0 1 3 0l2 2a2 2 0 0 1 0 3L10 19l-6 1Z"/>',
    "bulb": '<path d="M9 18h6m-6 3h6m-6-6a7 7 0 1 1 6 0v3H9v-3Z"/>',
    "folder": '<path d="M3 7V4h6l2 3h10v13H3V7Z"/>',
    "bolt": '<path d="m13 2-9 12h7l-1 8 10-13h-7l0-7Z"/>',

    "grid": '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
    "cases": '<rect x="5" y="4" width="15" height="17" rx="2"/><path d="M9 4V2M9 9h7M9 13h7M9 17h4"/>',
    "chart": '<path d="M4 3v17h17M9 15v-4M14 15V7M19 15V4"/>',
    "building": '<path d="M3 21h18M5 21V7l7-4 7 4v14M9 9h1m4 0h1M9 13h1m4 0h1M10 21v-4h4v4"/>',
    "category": '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><circle cx="17.5" cy="17.5" r="3.5"/>',
    "users": '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 5"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
    "chevron": '<path d="m8 10 4 4 4-4"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "logout": '<path d="M9 4H4v16h5M9 12h12m-4-4 4 4-4 4"/>',
}

@register.simple_tag
def ui_icon(name):
    return format_html('<svg class="icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>', mark_safe(PATHS.get(name, PATHS["cases"])))
