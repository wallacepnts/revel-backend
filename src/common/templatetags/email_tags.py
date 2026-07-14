from django import template

from common.models import SiteSettings

register = template.Library()


@register.simple_tag
def email_logo_url() -> str:
    """Absolute URL for the DuRock RJ logo, used in outgoing email headers."""
    return f"{SiteSettings.get_solo().frontend_base_url.rstrip('/')}/logo-mark.png"
