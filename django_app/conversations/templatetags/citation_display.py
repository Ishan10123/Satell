import html
import ipaddress
import re
from urllib.parse import urlsplit

from django import template

register = template.Library()


def _clean(value):
    if not isinstance(value, str):
        return ""
    value = html.unescape(value)
    # Markdown renderers and chunk metadata normalizers can insert spacing
    # inside an explicit heading anchor, e.g. "{ #section-name }".
    value = re.sub(r"\s*\{\s*#\s*[A-Za-z0-9_-]+\s*\}", "", value)
    value = re.sub(r"\{\{.*?\}\}|<%.*?%>", "", value)
    value = " ".join("".join(c for c in value if ord(c) >= 32 or c in "\t\n").split())
    return value.strip(" \t\r\n-–—|:")


@register.filter
def citation_display_title(value, section=""):
    title = _clean(value)
    clean_section = _clean(section)
    if title and clean_section and title.casefold() == clean_section.casefold():
        clean_section = ""
    return title or clean_section or "Source document"


@register.filter
def citation_display_section(value, title=""):
    section = _clean(value)
    if section.casefold() == _clean(title).casefold():
        return ""
    return section


@register.filter
def safe_source_reference(value):
    if not isinstance(value, str):
        return ""
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return ""
    try:
        if not ipaddress.ip_address(parsed.hostname).is_global:
            return ""
    except ValueError:
        if parsed.hostname.lower() == "localhost" or "." not in parsed.hostname:
            return ""
    from urllib.parse import urlunsplit
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
