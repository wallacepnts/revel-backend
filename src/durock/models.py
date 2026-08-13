"""Models for the DuRock RJ fork.

Every relation to an upstream model is declared from this side, so the
migrations land in ``durock/`` and ``events/migrations/`` stays untouched.

On Pix specifically: a Pix tier is an ``OFFLINE`` tier. The whole purchase
flow already branches on "is it Stripe or not" (``events/service/guest.py``,
``refund_service``, ``revenue_aggregation``), so an offline tier already gets
the right behaviour end to end — no automatic refund, revenue counted outside
Stripe, ticket left PENDING until the organizer confirms. What is missing, and
all that lives here, is the BR Code the buyer pays and the reference the
organizer reconciles it by.
"""

import typing as t
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from common.models import TimeStampedModel

from .pix import build_pix_payload, generate_pix_qr_code_png


class OrganizationPixConfig(TimeStampedModel):
    """The Pix key an organization receives ticket money on.

    A OneToOne from this side rather than a field on ``events.Organization``:
    same ``organization.pix_config`` access, no migration in ``events/``.
    """

    organization = models.OneToOneField(
        "events.Organization",
        on_delete=models.CASCADE,
        related_name="pix_config",
    )
    pix_key = models.CharField(
        max_length=140,
        help_text="CPF, CNPJ, e-mail, telefone ou chave aleatória (EVP) que recebe o pagamento.",
    )
    # The BR Code spec caps these two fields, and readers truncate silently past
    # the limit — so cap them at the source instead of surprising the organizer.
    merchant_name = models.CharField(
        max_length=25,
        help_text="Nome do recebedor como aparece no app do banco (máx. 25 caracteres).",
    )
    merchant_city = models.CharField(
        max_length=15,
        help_text="Cidade do recebedor (máx. 15 caracteres).",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Desmarque para parar de oferecer Pix sem apagar a chave.",
    )

    class Meta:
        verbose_name = "configuração Pix"
        verbose_name_plural = "configurações Pix"

    def __str__(self) -> str:
        return f"Pix de {self.organization}"

    def build_payload(self, *, txid: str, amount: Decimal | None) -> str:
        """Build the "copia e cola" payload for one charge against this key."""
        return build_pix_payload(
            pix_key=self.pix_key,
            merchant_name=self.merchant_name,
            merchant_city=self.merchant_city,
            txid=txid,
            amount=amount,
        )


class PixCharge(TimeStampedModel):
    """The BR Code a buyer pays for one ticket.

    Deliberately has **no status of its own**: the ticket's status is the
    truth. The organizer confirms payment through the endpoint that already
    exists (``…/tickets/{id}/confirm-payment``), which flips the ticket from
    PENDING to ACTIVE. A second status here would be a second answer to the
    same question, and the two would drift.
    """

    ticket = models.OneToOneField(
        "events.Ticket",
        on_delete=models.CASCADE,
        related_name="pix_charge",
    )
    txid = models.CharField(
        max_length=25,
        unique=True,
        editable=False,
        help_text="Referência que o organizador vê no extrato para conciliar o pagamento.",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
        help_text="Valor congelado na emissão do QR.",
    )
    # Frozen on purpose: the tier's price can change after the buyer has already
    # saved the QR, and a code that stops matching what the organizer expects is
    # worse than a stale price.
    payload = models.TextField(editable=False)

    class Meta:
        verbose_name = "cobrança Pix"
        verbose_name_plural = "cobranças Pix"

    def __str__(self) -> str:
        return f"Pix {self.txid} ({self.amount})"

    def clean(self) -> None:
        """Reject a charge on a tier that is not paid outside the platform."""
        super().clean()
        from events.models import TicketTier

        if self.ticket_id and self.ticket.tier.payment_method != TicketTier.PaymentMethod.OFFLINE:
            raise ValidationError({"ticket": "Pix só se aplica a lotes com pagamento fora da plataforma (OFFLINE)."})

    def qr_code_png(self) -> bytes:
        """Render this charge's payload as a PNG QR code."""
        return generate_pix_qr_code_png(self.payload)

    @classmethod
    def issue_for(cls, ticket: t.Any, *, amount: Decimal) -> "PixCharge | None":
        """Create the charge for a ticket, or return None when Pix does not apply.

        Returns None — rather than raising — when the organization has no active
        Pix key: an organizer who never configured Pix is the normal case, not
        an error, and the checkout must go on working exactly as before.
        """
        config = OrganizationPixConfig.objects.filter(organization=ticket.event.organization, is_active=True).first()
        if config is None:
            return None

        txid = ticket.id.hex[:25]
        return cls.objects.create(
            ticket=ticket,
            txid=txid,
            amount=amount,
            payload=config.build_payload(txid=txid, amount=amount),
        )
