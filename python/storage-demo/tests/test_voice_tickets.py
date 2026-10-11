import pytest

from voice_tickets import VoiceTicketError, VoiceTicketStore


def test_issue_and_consume_ticket():
    store = VoiceTicketStore()

    ticket = store.issue("tenant-a", "user-a")
    identity = store.consume(ticket)

    assert identity.tenant_id == "tenant-a"
    assert identity.user_id == "user-a"


def test_ticket_cannot_be_replayed():
    store = VoiceTicketStore()

    ticket = store.issue("tenant-a", "user-a")
    store.consume(ticket)

    with pytest.raises(VoiceTicketError):
        store.consume(ticket)


def test_unknown_ticket_rejected():
    store = VoiceTicketStore()

    with pytest.raises(VoiceTicketError):
        store.consume("unknown")


def test_empty_ticket_rejected():
    store = VoiceTicketStore()

    with pytest.raises(VoiceTicketError):
        store.consume("")


def test_missing_identity_rejected():
    store = VoiceTicketStore()

    with pytest.raises(VoiceTicketError):
        store.issue("", "user-a")


def test_ticket_capacity_enforced():
    store = VoiceTicketStore(max_tickets=1)

    store.issue("tenant-a", "user-a")

    with pytest.raises(VoiceTicketError):
        store.issue("tenant-b", "user-b")


def test_expired_ticket_rejected(monkeypatch):
    clock = [100.0]

    monkeypatch.setattr(
        "voice_tickets.time.monotonic",
        lambda: clock[0],
    )

    store = VoiceTicketStore(ttl_seconds=5)

    ticket = store.issue("tenant-a", "user-a")

    clock[0] = 106.0

    with pytest.raises(VoiceTicketError):
        store.consume(ticket)


def test_invalid_store_configuration():
    with pytest.raises(ValueError):
        VoiceTicketStore(ttl_seconds=0)

    with pytest.raises(ValueError):
        VoiceTicketStore(max_tickets=0)
