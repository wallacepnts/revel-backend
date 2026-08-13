"""Tests for the Pix models.

The behaviour worth protecting is not "a row was written" — it is that an
organizer who never configured Pix keeps the checkout they had, that a charge
cannot attach to a Stripe tier, and that the payload the buyer saved never
changes underneath them.
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from accounts.models import RevelUser
from durock.models import OrganizationPixConfig, PixCharge
from events.models import Event, Organization, Ticket, TicketTier

pytestmark = pytest.mark.django_db


@pytest.fixture
def pix_config(organization: Organization) -> OrganizationPixConfig:
    return OrganizationPixConfig.objects.create(
        organization=organization,
        pix_key="durock@example.com",
        merchant_name="DuRock RJ",
        merchant_city="Rio de Janeiro",
    )


def test_issue_for_returns_none_without_config(offline_ticket: Ticket) -> None:
    """An organizer with no Pix key must keep exactly the checkout they had."""
    assert PixCharge.issue_for(offline_ticket, amount=Decimal("50.00")) is None
    assert PixCharge.objects.count() == 0


def test_issue_for_returns_none_when_config_is_inactive(
    offline_ticket: Ticket, pix_config: OrganizationPixConfig
) -> None:
    """Unchecking is_active stops new charges without deleting the key."""
    pix_config.is_active = False
    pix_config.save()

    assert PixCharge.issue_for(offline_ticket, amount=Decimal("50.00")) is None


def test_issue_for_builds_a_payable_charge(offline_ticket: Ticket, pix_config: OrganizationPixConfig) -> None:
    charge = PixCharge.issue_for(offline_ticket, amount=Decimal("50.00"))

    assert charge is not None
    assert charge.txid == offline_ticket.id.hex[:25]
    assert charge.amount == Decimal("50.00")
    # The payload carries the key and the amount the buyer is meant to send.
    # Field 54 is the amount, as id + length + value: "54" + "05" + "50.00".
    assert pix_config.pix_key in charge.payload
    assert "540550.00" in charge.payload
    # Ends with the CRC16 field the spec mandates: "6304" + four hex digits.
    assert charge.payload[-8:-4] == "6304"
    int(charge.payload[-4:], 16)


def test_charge_is_rejected_on_a_stripe_tier(online_ticket: Ticket, pix_config: OrganizationPixConfig) -> None:
    """Pix is money outside the platform; an ONLINE tier is Stripe's job."""
    with pytest.raises(ValidationError):
        PixCharge.issue_for(online_ticket, amount=Decimal("50.00"))

    assert PixCharge.objects.count() == 0


def test_payload_survives_a_tier_price_change(offline_ticket: Ticket, pix_config: OrganizationPixConfig) -> None:
    """The QR the buyer saved must keep matching what the organizer expects."""
    charge = PixCharge.issue_for(offline_ticket, amount=Decimal("50.00"))
    assert charge is not None
    original_payload = charge.payload

    offline_ticket.tier.price = Decimal("80.00")
    offline_ticket.tier.save()

    charge.refresh_from_db()
    assert charge.payload == original_payload
    assert charge.amount == Decimal("50.00")


def test_qr_code_png_renders(offline_ticket: Ticket, pix_config: OrganizationPixConfig) -> None:
    charge = PixCharge.issue_for(offline_ticket, amount=Decimal("50.00"))
    assert charge is not None

    png = charge.qr_code_png()
    assert png.startswith(b"\x89PNG\r\n\x1a\n")


def test_one_charge_per_ticket(offline_ticket: Ticket, pix_config: OrganizationPixConfig) -> None:
    """A second QR for the same ticket would be a second amount to reconcile."""
    PixCharge.issue_for(offline_ticket, amount=Decimal("50.00"))

    with pytest.raises(Exception):
        PixCharge.issue_for(offline_ticket, amount=Decimal("50.00"))


def test_config_reachable_from_the_organization(organization: Organization, pix_config: OrganizationPixConfig) -> None:
    """The reverse accessor reads like a field on Organization, which is the point."""
    organization.refresh_from_db()
    assert organization.pix_config == pix_config


def test_charge_reachable_from_the_ticket(offline_ticket: Ticket, pix_config: OrganizationPixConfig) -> None:
    charge = PixCharge.issue_for(offline_ticket, amount=Decimal("50.00"))

    offline_ticket.refresh_from_db()
    assert offline_ticket.pix_charge == charge


def test_event_and_user_fixtures_are_wired(event: Event, buyer: RevelUser, offline_tier: TicketTier) -> None:
    """Guard the fixtures themselves: a silently broken tier would fake a pass."""
    assert offline_tier.payment_method == TicketTier.PaymentMethod.OFFLINE
    assert event.organization.owner != buyer
