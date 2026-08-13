"""Fixtures for the durock app.

Deliberately self-contained: pytest only picks up a conftest from the test's
own directory upwards, so the ones under ``events/tests`` are out of reach here.
"""

import typing as t

import pytest
from django.utils import timezone

from accounts.models import RevelUser
from events.models import Event, Organization, Ticket, TicketTier


@pytest.fixture
def buyer(django_user_model: t.Type[RevelUser]) -> RevelUser:
    return django_user_model.objects.create_user(
        username="pix_buyer", email="buyer@example.com", password="pass", email_verified=True
    )


@pytest.fixture
def organizer(django_user_model: t.Type[RevelUser]) -> RevelUser:
    return django_user_model.objects.create_user(
        username="pix_organizer", email="organizer@example.com", password="pass", email_verified=True
    )


@pytest.fixture
def organization(organizer: RevelUser) -> Organization:
    return Organization.objects.create(name="DuRock", slug="durock", owner=organizer)


@pytest.fixture
def event(organization: Organization) -> Event:
    return Event.objects.create(
        organization=organization,
        name="Show",
        slug="show",
        event_type=Event.EventType.PUBLIC,
        visibility=Event.Visibility.PUBLIC,
        max_attendees=100,
        start=timezone.now(),
        status="open",
        requires_ticket=True,
    )


@pytest.fixture
def offline_tier(event: Event) -> TicketTier:
    """The kind of tier Pix applies to: money that changes hands outside Stripe."""
    return TicketTier.objects.create(
        event=event, name="Pista", price=50.00, payment_method=TicketTier.PaymentMethod.OFFLINE
    )


@pytest.fixture
def online_tier(event: Event) -> TicketTier:
    return TicketTier.objects.create(
        event=event, name="Online", price=50.00, payment_method=TicketTier.PaymentMethod.ONLINE
    )


@pytest.fixture
def offline_ticket(event: Event, buyer: RevelUser, offline_tier: TicketTier) -> Ticket:
    return Ticket.objects.create(event=event, user=buyer, tier=offline_tier, guest_name=buyer.get_display_name())


@pytest.fixture
def online_ticket(event: Event, buyer: RevelUser, online_tier: TicketTier) -> Ticket:
    return Ticket.objects.create(event=event, user=buyer, tier=online_tier, guest_name=buyer.get_display_name())
