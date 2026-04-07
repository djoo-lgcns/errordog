"""DAP proxy server — bidirectional forwarding between IDE and debugpy."""

import asyncio
import logging

from errordog.dap.mock import MockAdapter
from errordog.dap.protocol import read_message, write_message
from errordog.dap.session import DebugSession, StackFrame, Variable

logger = logging.getLogger(__name__)

DAP_PROXY_PORT = 5679
DEBUGPY_HOST = "localhost"
DEBUGPY_PORT = 5678


class DapServer:
    """Async TCP server that routes IDE connections to proxy or mock mode."""

    def __init__(self) -> None:
        self._active = False

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        if self._active:
            logger.warning("DAP: rejecting connection — session already active")
            writer.close()
            return

        self._active = True
        addr = writer.get_extra_info("peername")
        logger.info("DAP: IDE connected from %s", addr)

        try:
            # Buffer messages until we see 'attach' to decide mode.
            # Respond to 'initialize' immediately so the IDE doesn't time out
            # while waiting for a response before sending 'attach'.
            buffered: list[dict] = []
            proxy_seq = 9000  # high seq to avoid colliding with IDE/debugpy seqs

            while True:
                msg = await read_message(reader)
                buffered.append(msg)
                command = msg.get("command")

                if command == "initialize":
                    # Acknowledge immediately — IDE won't send 'attach' until it gets this
                    await write_message(writer, {
                        "seq": proxy_seq,
                        "type": "response",
                        "request_seq": msg["seq"],
                        "command": "initialize",
                        "success": True,
                        "body": {"supportsConfigurationDoneRequest": True},
                    })
                    proxy_seq += 1

                elif command == "attach":
                    args = msg.get("arguments", {})
                    logger.info("DAP: attach arguments: %s", args)
                    error_id = args.get("error_id") or None
                    if error_id:
                        logger.info("DAP: mock mode — error_id=%s", error_id)
                        await self._run_mock(buffered, reader, writer, error_id)
                    else:
                        logger.info(
                            "DAP: proxy mode → debugpy at %s:%d", DEBUGPY_HOST, DEBUGPY_PORT
                        )
                        await self._run_proxy(buffered, reader, writer)
                    break

        except (EOFError, ConnectionResetError):
            logger.info("DAP: IDE disconnected during handshake")
        finally:
            self._active = False
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _run_mock(
        self,
        buffered: list[dict],
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        error_id: str,
    ) -> None:
        """Run a mock debug session from an ESF snapshot."""
        adapter = MockAdapter(error_id)
        # Replay buffered messages — skip 'initialize' since proxy already responded
        for msg in buffered:
            if msg.get("command") == "initialize":
                continue
            done = await adapter.process(msg, writer)
            if done:
                return
        # Continue with live reader
        try:
            while True:
                msg = await read_message(reader)
                done = await adapter.process(msg, writer)
                if done:
                    break
        except (EOFError, ConnectionResetError):
            pass

    async def _run_proxy(
        self,
        buffered: list[dict],
        ide_reader: asyncio.StreamReader,
        ide_writer: asyncio.StreamWriter,
    ) -> None:
        """Proxy messages between IDE and debugpy, passively caching state."""
        try:
            dbg_reader, dbg_writer = await asyncio.open_connection(DEBUGPY_HOST, DEBUGPY_PORT)
        except ConnectionRefusedError:
            logger.error(
                "DAP: cannot connect to debugpy at %s:%d", DEBUGPY_HOST, DEBUGPY_PORT
            )
            return

        session = DebugSession(mode="proxy")
        pending: dict[int, str] = {}  # request_seq → command (for response correlation)

        # Forward buffered messages to debugpy.
        # Track initialize seq so we can discard debugpy's duplicate response
        # (proxy already responded to initialize during handshake).
        init_seq: int | None = None
        for msg in buffered:
            pending[msg["seq"]] = msg.get("command", "")
            if msg.get("command") == "initialize":
                init_seq = msg["seq"]
            await write_message(dbg_writer, msg)

        async def ide_to_debugpy() -> None:
            try:
                while True:
                    msg = await read_message(ide_reader)
                    pending[msg["seq"]] = msg.get("command", "")
                    await write_message(dbg_writer, msg)
            except (EOFError, ConnectionResetError):
                pass

        async def debugpy_to_ide() -> None:
            try:
                while True:
                    msg = await read_message(dbg_reader)
                    # Discard debugpy's initialize response — proxy already sent one
                    if (
                        msg.get("type") == "response"
                        and msg.get("command") == "initialize"
                        and msg.get("request_seq") == init_seq
                    ):
                        pending.pop(init_seq, None)
                        continue
                    _intercept(msg, session, pending)
                    await write_message(ide_writer, msg)
            except (EOFError, ConnectionResetError):
                pass

        await asyncio.gather(ide_to_debugpy(), debugpy_to_ide())
        try:
            dbg_writer.close()
            await dbg_writer.wait_closed()
        except Exception:
            pass

    async def start(self) -> None:
        server = await asyncio.start_server(
            self.handle_client,
            "localhost",
            DAP_PROXY_PORT,
        )
        logger.info("DAP proxy listening on localhost:%d", DAP_PROXY_PORT)
        async with server:
            await server.serve_forever()


def _intercept(msg: dict, session: DebugSession, pending: dict[int, str]) -> None:
    """Passively snoop on debugpy→IDE messages to cache live debug state."""
    msg_type = msg.get("type")

    if msg_type == "event":
        if msg.get("event") == "stopped":
            session.thread_id = msg.get("body", {}).get("threadId")
            logger.debug("DAP: stopped — threadId=%s", session.thread_id)

    elif msg_type == "response" and msg.get("success"):
        req_seq = msg.get("request_seq", -1)
        command = pending.pop(req_seq, None)

        if command == "stackTrace":
            frames_data = msg.get("body", {}).get("stackFrames", [])
            session.stack_trace = [
                StackFrame(
                    id=f["id"],
                    name=f.get("name", ""),
                    line=f.get("line", 0),
                    source_path=f.get("source", {}).get("path"),
                )
                for f in frames_data
            ]
            if session.stack_trace:
                session.frame_id = session.stack_trace[0].id
            logger.debug("DAP: cached %d stack frames", len(session.stack_trace))

        elif command == "variables":
            variables_data = msg.get("body", {}).get("variables", [])
            session.variables[req_seq] = [
                Variable(
                    name=v.get("name", ""),
                    value=v.get("value", ""),
                    type=v.get("type"),
                    variables_reference=v.get("variablesReference", 0),
                )
                for v in variables_data
            ]
            logger.debug("DAP: cached %d variables", len(variables_data))


def run() -> None:
    """Entry point for `errordog dap`."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(DapServer().start())
