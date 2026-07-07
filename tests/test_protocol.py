"""Unit tests for the pure protocol logic (no BLE hardware required)."""

from additel_ble.protocol import ResponseBuffer, build_command


def test_single_line():
    buf = ResponseBuffer()
    assert buf.feed(b"ADDITEL,ADT226\r\n") == ["ADDITEL,ADT226"]


def test_fragmented_across_notifications():
    buf = ResponseBuffer()
    assert buf.feed(b"ADDI") == []
    assert buf.feed(b"TEL\r\n") == ["ADDITEL"]


def test_two_lines_in_one_chunk():
    buf = ResponseBuffer()
    assert buf.feed(b"CODE?\r\n1.2345\r\n") == ["CODE?", "1.2345"]


def test_mixed_terminators():
    buf = ResponseBuffer()
    assert buf.feed(b"a\rb\x00c\n") == ["a", "b", "c"]


def test_partial_stays_buffered():
    buf = ResponseBuffer()
    assert buf.feed(b"abc\r\ndef") == ["abc"]
    assert buf.feed(b"ghi\r\n") == ["defghi"]


def test_reset_discards_partial():
    buf = ResponseBuffer()
    assert buf.feed(b"partial") == []
    buf.reset()
    assert buf.feed(b"X\r\n") == ["X"]


def test_build_command():
    assert build_command("*IDN?") == b"*IDN?\r\n"
    assert build_command("*IDN?", prefix="@") == b"@*IDN?\r\n"
    assert build_command("A", terminator="\n") == b"A\n"
