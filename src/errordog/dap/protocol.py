"""DAP message framing — Content-Length header protocol (identical to LSP)."""

import asyncio
import json


async def read_message(reader: asyncio.StreamReader) -> dict:
    """Read one DAP message from the stream."""
    header = b""
    while not header.endswith(b"\r\n\r\n"):
        byte = await reader.read(1)
        if not byte:
            raise EOFError("Connection closed while reading DAP header")
        header += byte

    content_length: int | None = None
    for line in header.decode("utf-8").split("\r\n"):
        if line.startswith("Content-Length:"):
            content_length = int(line.split(":", 1)[1].strip())

    if content_length is None:
        raise ValueError(f"Missing Content-Length in DAP header: {header!r}")

    body = await reader.readexactly(content_length)
    return json.loads(body.decode("utf-8"))


def encode_message(msg: dict) -> bytes:
    """Encode a DAP message as bytes with Content-Length framing."""
    body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
    return header + body


async def write_message(writer: asyncio.StreamWriter, msg: dict) -> None:
    """Write one DAP message to the stream."""
    writer.write(encode_message(msg))
    await writer.drain()
