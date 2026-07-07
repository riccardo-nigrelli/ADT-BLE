"""Tests for characteristic resolution and write-mode selection (no hardware).

These lock in the fix for the ATT 0x0D ("Invalid Attribute Value Length")
error: the write must use write-without-response whenever the characteristic
supports it.
"""

from additel_ble import AdditelBLE
from additel_ble.protocol import DOC_NOTIFY_UUID


class FakeChar:
    def __init__(self, uuid, properties):
        self.uuid = uuid
        self.properties = list(properties)
        self.description = ""


class FakeService:
    uuid = "0000-service"
    description = ""

    def __init__(self, chars):
        self.characteristics = chars


class FakeServices:
    def __init__(self, chars):
        self._chars = chars

    def __iter__(self):
        yield FakeService(self._chars)

    def get_characteristic(self, uuid):
        for c in self._chars:
            if str(c.uuid).lower() == str(uuid).lower():
                return c
        return None


class FakeClient:
    def __init__(self, chars):
        self.services = FakeServices(chars)
        self.is_connected = True


def _resolve(chars, **kwargs):
    dev = AdditelBLE(**kwargs)
    dev._client = FakeClient(chars)
    dev._resolve_characteristics()
    return dev


def test_prefers_write_without_response_when_both_supported():
    char = FakeChar(DOC_NOTIFY_UUID, ["write", "write-without-response", "notify"])
    dev = _resolve([char])
    assert dev._write_response is False
    assert dev.write_uuid == DOC_NOTIFY_UUID
    assert dev.notify_uuid == DOC_NOTIFY_UUID


def test_uses_write_without_response_only():
    char = FakeChar(DOC_NOTIFY_UUID, ["write-without-response", "notify"])
    dev = _resolve([char])
    assert dev._write_response is False


def test_uses_with_response_when_only_write():
    char = FakeChar(DOC_NOTIFY_UUID, ["write", "notify"])
    dev = _resolve([char])
    assert dev._write_response is True


def test_autodiscovers_when_documented_uuid_absent():
    # A device that exposes different UUIDs -> documented lookup fails,
    # auto-discovery must still find the notify+write characteristic.
    char = FakeChar("aaaa-1234-different", ["notify", "write-without-response"])
    dev = _resolve([char])
    assert dev.notify_uuid == "aaaa-1234-different"
    assert dev.write_uuid == "aaaa-1234-different"
    assert dev._write_response is False


def test_separate_notify_and_write_characteristics():
    notify = FakeChar("uuid-notify", ["notify"])
    write = FakeChar("uuid-write", ["write"])
    dev = _resolve([notify, write])
    assert dev.notify_uuid == "uuid-notify"
    assert dev.write_uuid == "uuid-write"
    assert dev._write_response is True
