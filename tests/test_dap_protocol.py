"""Tests for errordog.dap.protocol — DAP Content-Length framing."""

import asyncio
import json

import pytest

from errordog.dap.protocol import encode_message, read_message, write_message


def _run_read(data: bytes) -> dict:
    """Create a StreamReader inside the event loop and read one message."""
    async def _inner() -> dict:
        reader = asyncio.StreamReader()
        reader.feed_data(data)
        reader.feed_eof()
        return await read_message(reader)
    return asyncio.run(_inner())


class FakeWriter:
    def __init__(self) -> None:
        self._buf = bytearray()

    def write(self, data: bytes) -> None:
        self._buf.extend(data)

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        pass

    @property
    def written(self) -> bytes:
        return bytes(self._buf)


class TestEncodeMessage:
    def test_includes_content_length_header(self) -> None:
        msg = {"seq": 1, "type": "request", "command": "initialize"}
        encoded = encode_message(msg)
        assert b"Content-Length:" in encoded
        assert b"\r\n\r\n" in encoded

    def test_round_trip(self) -> None:
        msg = {"seq": 1, "type": "event", "event": "stopped", "body": {"threadId": 3}}
        encoded = encode_message(msg)
        # Parse manually
        header, body = encoded.split(b"\r\n\r\n", 1)
        content_length = int(header.split(b"Content-Length: ")[1])
        assert len(body) == content_length
        assert json.loads(body) == msg

    def test_unicode_in_body(self) -> None:
        msg = {"message": "한글 에러"}
        encoded = encode_message(msg)
        _, body = encoded.split(b"\r\n\r\n", 1)
        assert json.loads(body.decode("utf-8"))["message"] == "한글 에러"


class TestReadMessage:
    def test_reads_single_message(self) -> None:
        msg = {"seq": 1, "type": "request", "command": "initialize", "arguments": {}}
        result = _run_read(encode_message(msg))
        assert result == msg

    def test_reads_multiple_messages_sequentially(self) -> None:
        msg1 = {"seq": 1, "type": "request", "command": "initialize"}
        msg2 = {"seq": 2, "type": "request", "command": "attach", "arguments": {}}
        data = encode_message(msg1) + encode_message(msg2)

        async def _inner() -> tuple[dict, dict]:
            reader = asyncio.StreamReader()
            reader.feed_data(data)
            reader.feed_eof()
            r1 = await read_message(reader)
            r2 = await read_message(reader)
            return r1, r2

        result1, result2 = asyncio.run(_inner())
        assert result1 == msg1
        assert result2 == msg2

    def test_eof_raises(self) -> None:
        async def _inner() -> None:
            reader = asyncio.StreamReader()
            reader.feed_eof()
            await read_message(reader)

        with pytest.raises(EOFError):
            asyncio.run(_inner())

    def test_missing_content_length_raises(self) -> None:
        with pytest.raises(ValueError, match="Missing Content-Length"):
            _run_read(b"X-Custom: value\r\n\r\n{}")


class TestWriteMessage:
    def test_writes_encoded_message(self) -> None:
        msg = {"seq": 1, "type": "event", "event": "initialized"}
        writer = FakeWriter()
        asyncio.run(write_message(writer, msg))  # type: ignore[arg-type]
        assert b"Content-Length:" in writer.written
        _, body = writer.written.split(b"\r\n\r\n", 1)
        assert json.loads(body) == msg
