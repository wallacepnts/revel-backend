"""Tests for the Pix BR Code payload/QR generation (events.utils.pix)."""

from decimal import Decimal

from events.utils.pix import _crc16_ccitt, build_pix_payload, generate_pix_qr_code_png


def _parse_tlv(payload: str) -> dict[str, str]:
    """Parse a flat (non-nested) TLV payload into {tag: value}, for assertions."""
    fields: dict[str, str] = {}
    i = 0
    while i < len(payload):
        tag, length = payload[i : i + 2], int(payload[i + 2 : i + 4])
        fields[tag] = payload[i + 4 : i + 4 + length]
        i += 4 + length
    return fields


class TestBuildPixPayload:
    def test_matches_known_good_reference_payload(self) -> None:
        """Byte-for-byte parity with a real Pix BR Code generator, for the same inputs
        (cross-checked against the `pixcore` library during development)."""
        payload = build_pix_payload(
            pix_key="11144477735",
            merchant_name="DUROCK RJ EVENTOS",
            merchant_city="RIO DE JANEIRO",
            txid="EVT12AB34CD",
            amount=Decimal("99.90"),
        )
        assert payload == (
            "00020126330014BR.GOV.BCB.PIX011111144477735520400005303986540599.90"
            "5802BR5917DUROCK RJ EVENTOS6014RIO DE JANEIRO62150511EVT12AB34CD6304AEE3"
        )

    def test_omits_amount_field_for_open_amount(self) -> None:
        """No amount (e.g. PWYC tiers) must omit field 54 entirely, not send '54000'."""
        payload = build_pix_payload(
            pix_key="org@example.com",
            merchant_name="Org",
            merchant_city="Rio de Janeiro",
            txid="ref1",
            amount=None,
        )
        assert "5204" in payload  # merchant category code still present
        assert _parse_tlv(payload).get("54") is None

    def test_strips_accents_and_uppercases_merchant_fields(self) -> None:
        payload = build_pix_payload(
            pix_key="org@example.com",
            merchant_name="Música & Cerveja Ltda",
            merchant_city="São Conrado",
            txid="ref1",
        )
        assert "MUSICA & CERVEJA LTDA" in payload
        assert "SAO CONRADO" in payload

    def test_truncates_merchant_name_to_25_chars(self) -> None:
        payload = build_pix_payload(
            pix_key="org@example.com",
            merchant_name="A" * 40,
            merchant_city="Rio de Janeiro",
            txid="ref1",
        )
        assert "59" + "25" + "A" * 25 in payload

    def test_truncates_merchant_city_to_15_chars(self) -> None:
        payload = build_pix_payload(
            pix_key="org@example.com",
            merchant_name="Org",
            merchant_city="B" * 30,
            txid="ref1",
        )
        assert "60" + "15" + "B" * 15 in payload

    def test_txid_strips_non_alphanumeric_and_truncates_to_25(self) -> None:
        payload = build_pix_payload(
            pix_key="org@example.com",
            merchant_name="Org",
            merchant_city="Rio de Janeiro",
            txid="abc-123!!extra_chars_beyond_25_limit_here",
        )
        expected_txid = "abc123extracharsbeyond25l"
        assert len(expected_txid) == 25
        assert f"0525{expected_txid}" in payload

    def test_empty_txid_falls_back_to_asterisks(self) -> None:
        payload = build_pix_payload(
            pix_key="org@example.com",
            merchant_name="Org",
            merchant_city="Rio de Janeiro",
            txid="",
        )
        assert "0503***" in payload

    def test_payload_ends_with_valid_crc16(self) -> None:
        """The CRC in the payload must match a fresh recomputation over the same prefix."""
        payload = build_pix_payload(
            pix_key="org@example.com",
            merchant_name="Org",
            merchant_city="Rio de Janeiro",
            txid="ref1",
            amount=Decimal("10.00"),
        )
        prefix, crc = payload[:-4], payload[-4:]
        assert _crc16_ccitt(prefix) == crc


class TestGeneratePixQrCodePng:
    def test_returns_valid_png_bytes(self) -> None:
        payload = build_pix_payload(
            pix_key="org@example.com",
            merchant_name="Org",
            merchant_city="Rio de Janeiro",
            txid="ref1",
            amount=Decimal("10.00"),
        )
        png_bytes = generate_pix_qr_code_png(payload)
        assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(png_bytes) > 100
