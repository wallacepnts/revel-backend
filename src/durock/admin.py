"""Django admin for the DuRock RJ fork models."""

import typing as t

from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from durock.models import OrganizationPixConfig, PixCharge


@admin.register(OrganizationPixConfig)
class OrganizationPixConfigAdmin(ModelAdmin):  # type: ignore[misc]
    """Where an organizer registers the Pix key their ticket money lands on."""

    list_display = ("organization", "pix_key", "merchant_name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("organization__name", "pix_key", "merchant_name")
    autocomplete_fields = ("organization",)


@admin.register(PixCharge)
class PixChargeAdmin(ModelAdmin):  # type: ignore[misc]
    """Read-only view of issued charges, for reconciling a bank statement.

    Everything is read-only on purpose: editing an issued charge would change
    the amount or reference after the buyer already saved the QR code. To
    settle a payment, confirm the ticket — that is the one place the state
    lives.
    """

    list_display = ("txid", "ticket_status", "amount", "created_at")
    list_filter = ("created_at", "ticket__status")
    search_fields = ("txid", "ticket__user__email", "ticket__event__name")
    readonly_fields = ("ticket", "txid", "amount", "payload", "created_at", "updated_at")
    date_hierarchy = "created_at"

    @admin.display(description="ingresso")
    def ticket_status(self, obj: PixCharge) -> str:
        """Show the ticket's status, which is what says whether the money arrived."""
        return format_html("{} — {}", obj.ticket.event.name, obj.ticket.get_status_display())

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Charges are issued by the checkout, never by hand."""
        return False

    def has_change_permission(self, request: HttpRequest, obj: t.Any = None) -> bool:
        """A charge is immutable once issued."""
        return False
