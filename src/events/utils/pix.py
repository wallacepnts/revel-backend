"""Pix BR Code (EMV QR Code) generation for the DuRock RJ Pix payment method.

Builds the "Pix Copia e Cola" payload and QR code image per the Central Bank
of Brazil's static QR code spec (Manual de Padrões para Iniciação do Pix).
No external Pix API/PSP is involved — this is a static QR pointing at the
organization's own Pix key, so payment confirmation is always manual (the
same flow already used for OFFLINE ticket tiers).

Reference: https://www.bcb.gov.br/estabilidadefinanceira/pix (QR code payload spec).
"""

import io
import unicodedata
from decimal import Decimal

import qrcode

_GUI = "BR.GOV.BCB.PIX"
_MERCHANT_CATEGORY_CODE = "0000"
_TRANSACTION_CURRENCY_BRL = "986"
_COUNTRY_CODE = "BR"
_CRC16_POLYNOMIAL = 0x1021
_CRC16_INITIAL = 0xFFFF


def _tlv(field_id: str, value: str) -> str:
    """Build one Tag-Length-Value field: 2-digit id + 2-digit length + value."""
    return f"{field_id}{len(value):02d}{value}"


def _sanitize(value: str, max_length: int) -> str:
    """Strip diacritics/non-ASCII and truncate for the strictest Pix-reader compatibility.

    The spec technically allows a wider charset, but not every bank's reader handles it
    consistently, so this normalizes to plain uppercase ASCII like most PSPs do.
    """
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return ascii_value.strip().upper()[:max_length]


def _crc16_ccitt(payload: str) -> str:
    """CRC16/CCITT-FALSE checksum (poly 0x1021, init 0xFFFF) as 4 uppercase hex digits.

    This is the specific CRC16 variant the Pix spec mandates for the trailing "63" field.
    """
    crc = _CRC16_INITIAL
    for byte in payload.encode("ascii"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ _CRC16_POLYNOMIAL) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def build_pix_payload(
    *,
    pix_key: str,
    merchant_name: str,
    merchant_city: str,
    txid: str,
    amount: Decimal | None = None,
) -> str:
    """Build the static Pix "Copia e Cola" payload string.

    Args:
        pix_key: The receiving Pix key (CPF, CNPJ, email, phone, or random/EVP key).
        merchant_name: Receiver display name, truncated to 25 chars (spec limit).
        merchant_city: Receiver city, truncated to 15 chars (spec limit).
        txid: Alphanumeric reference id, max 25 chars — used to look the payment back up
            in the platform (event + buyer), since the field itself is too short to hold
            both. Falls back to "***" (spec's "no reference") if empty.
        amount: Fixed amount to pre-fill, or None to let the payer enter it (PWYC tiers).

    Returns:
        The complete payload string, CRC16 checksum included.
    """
    merchant_account_info = _tlv("00", _GUI) + _tlv("01", pix_key)
    txid_value = "".join(c for c in txid if c.isalnum())[:25] or "***"

    fields = [
        _tlv("00", "01"),  # Payload Format Indicator
        _tlv("26", merchant_account_info),  # Merchant Account Information — Pix
        _tlv("52", _MERCHANT_CATEGORY_CODE),
        _tlv("53", _TRANSACTION_CURRENCY_BRL),
    ]
    if amount is not None:
        fields.append(_tlv("54", f"{amount:.2f}"))
    fields.extend(
        [
            _tlv("58", _COUNTRY_CODE),
            _tlv("59", _sanitize(merchant_name, 25) or "NA"),
            _tlv("60", _sanitize(merchant_city, 15) or "NA"),
            _tlv("62", _tlv("05", txid_value)),  # Additional Data Field — Reference Label
        ]
    )
    payload_without_crc = "".join(fields) + "6304"
    return payload_without_crc + _crc16_ccitt(payload_without_crc)


def generate_pix_qr_code_png(payload: str) -> bytes:
    """Render a Pix payload as a PNG QR code image, returned as raw bytes."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, "PNG")
    return buffer.getvalue()
