"""Templates for system-level notifications."""

from django.conf import settings
from django.utils.translation import gettext as _

from notifications.enums import NotificationType
from notifications.models import Notification
from notifications.service.templates.base import NotificationTemplate
from notifications.service.templates.registry import register_template


class SystemAnnouncementTemplate(NotificationTemplate):
    """Template for SYSTEM_ANNOUNCEMENT notification."""

    def get_in_app_title(self, notification: Notification) -> str:
        """Get title for in-app display."""
        title = notification.context.get("announcement_title") or _("System Announcement")
        return str(title)

    def get_email_subject(self, notification: Notification) -> str:
        """Get email subject."""
        title = notification.context.get("announcement_title") or _("System Announcement")
        return _("%(site_name)s - %(title)s") % {"site_name": settings.SITE_NAME, "title": title}


# Register templates
register_template(NotificationType.SYSTEM_ANNOUNCEMENT, SystemAnnouncementTemplate())
