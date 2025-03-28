import os
import glob
import json
import asyncio
import time
import shlex
from contextlib import asynccontextmanager
from functools import lru_cache
import logging
from typing import overload, AsyncIterator

from natsort import natsorted
import websockets
from anthropic._streaming import SSEDecoder, ServerSentEvent

from claude_inspect.process import ClaudeDesktopProcess
from claude_inspect.script_wrapper import load_script_file, raw_script


logger = logging.getLogger(__name__)


class SSEError(Exception):
    def __init__(
        self,
        addr: str,
        message: str,
    ):
        if message.lstrip().startswith("{"):
            try:
                data = json.loads(message)
                error_type = data.get("error", "unknown")
                message = data.get("message", message)
            except json.JSONDecodeError:
                error_type = "unknown"

        super().__init__(f"Error on SSE connection to {addr}: {error_type} {message}")


def _get_wd(exe_path: str) -> str:
    base_dir = os.path.dirname(exe_path)
    wd = glob.glob(os.path.join(base_dir, "app-*/"))
    # get newest version
    return natsorted(wd)[-1]


@lru_cache(1)
def _load_script_auto_approve():
    code = load_script_file("auto-approve.js")
    code = code.replace("$AUTO_APPROVE_TOOLS", json.dumps([]))
    return code


@lru_cache(1)
def _load_script_inject(addr: str, port: int):
    code = load_script_file("inject.js")
    code = code.replace("$SERVER_URL", json.dumps(f"ws://{addr}:{port}"))
    code = code.replace("$OPERATIONS", raw_script("_operations.js"))
    return code


class Client:
    """Claude for Desktop にスクリプトを注入して外部から操作を行うクラス"""

    def __init__(
        self,
        exe_path: str = r"%LOCALAPPDATA%\AnthropicClaude\claude.exe",
        wd: str | None = None,
        addr: str = "127.0.0.1",
        port: int = 9223,
    ):
        exe_path = os.path.expandvars(exe_path)

        if not wd:
            wd = _get_wd(exe_path)

        scripts = [
            _load_script_auto_approve(),
            _load_script_inject(addr, port),
        ]

        self.process = ClaudeDesktopProcess(
            exe_path,
            wd,
            "\n\n".join(scripts),
        )

        self.addr = addr
        self.port = port
        # self._server = None

        self.q_in: asyncio.Queue[dict] = asyncio.Queue(4)
        self.q_out: asyncio.Queue[bytes] = asyncio.Queue(4)
        self.__CLOSE = object()

    async def __handler(self, ws: websockets.ServerConnection):
        async def to_claude():
            while True:
                v = await self.q_in.get()
                if v is self.__CLOSE:
                    break
                logger.info(f"to claude: {v}")
                await ws.send(json.dumps(v))

        async def from_claude():
            async for msg in ws:
                logger.debug(f"from claude: {msg}")
                assert isinstance(msg, bytes), msg
                await self.q_out.put(msg)

        try:
            await asyncio.gather(to_claude(), from_claude())
        except websockets.exceptions.ConnectionClosedError:
            # connection closed
            pass
        except Exception as e:
            logger.exception("handler error")

    @overload
    async def get(self, *, get_ping=False) -> bytes: ...

    @overload
    async def get(self, timeout: float, *, get_ping=False) -> bytes | None: ...

    async def get(self, timeout: float | None = None, *, get_ping=False) -> bytes | None:
        t0 = time.time()
        while timeout is None or time.time() - t0 < timeout:
            try:
                v = self.q_out.get_nowait()
                if isinstance(v, bytes) and v.startswith(b"event: ping\n") and not get_ping:
                    continue
                return v
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.01)
        return None

    def clear_input_queue(self):
        while not self.q_in.empty():
            self.q_in.get_nowait()

    def clear_output_queue(self):
        while not self.q_out.empty():
            self.q_out.get_nowait()

    def clear_queue(self):
        self.clear_input_queue()
        self.clear_output_queue()

    async def serve_communicate(self, message: str) -> AsyncIterator[str]:
        with self.serve():
            async for msg in self.communicate(message):
                yield msg

    @asynccontextmanager
    async def serve(self):
        async with websockets.serve(self.__handler, self.addr, self.port):
            logger.info("websocket server launched")

            # wait for inject.js
            ping = await self.get(1.1, get_ping=True)
            if ping is None or not ping.startswith(b"event: ping"):
                logger.error("Failed to connect to Claude")
                raise RuntimeError("Failed to connect to Claude")

            yield

    async def communicate(self, message: str) -> AsyncIterator[ServerSentEvent]:
        self.clear_queue()

        await self.put_chat(message)
        await self.apply_chat()

        decoder = SSEDecoder()

        try:
            while True:
                msg = await self.get()
                msg = msg.decode()
                for line in msg.splitlines():
                    event = decoder.decode(line)
                    if not event:
                        continue
                    if event.event == "message_stop":
                        yield event
                        return
                    if event.event == "error":
                        raise SSEError(f"{self.addr}:{self.port}", event.data)
                    yield event
        finally:
            self.q_in.put_nowait(self.__CLOSE)

    @asynccontextmanager
    async def run(self):
        with self.process:
            async with self.serve():
                try:
                    yield self
                finally:
                    await self.q_in.put(self.__CLOSE)

    #
    # operations
    #

    async def apply_chat(self):
        async for event in self.call_op("apply_chat", []):
            if event.event == "error":
                raise SSEError(f"{self.addr}:{self.port}", event.data)

    async def put_chat(self, text: str):
        async for event in self.call_op("put_chat", [text]):
            if event.event == "error":
                raise SSEError(f"{self.addr}:{self.port}", event.data)

    async def clear_chat(self):
        async for event in self.call_op("clear_chat", []):
            if event.event == "error":
                raise SSEError(f"{self.addr}:{self.port}", event.data)

    async def call_op(self, name: str, args: list):
        self.clear_queue()
        await self.q_in.put({"op": name, "args": args})
        result = await self.get(get_ping=True)
        decoder = SSEDecoder()
        for line in result.decode().splitlines():
            event = decoder.decode(line)
            if not event:
                continue
            yield event


class ReplError(Exception):
    pass


class Command:
    def __init__(self, op: str, args: list):
        self.op = op
        self.args = args

    def __str__(self):
        return f"!{self.op} {' '.join(self.args)}"


class ClaudeRepl:
    def __init__(self, client: Client):
        self.client = client
        self._context = None

    @asynccontextmanager
    async def run(self):
        async with self.client.run():
            yield self

    def read(self) -> str:
        print(">", end=" ", flush=True)
        message = input()
        return message

    async def eval(self, message: str) -> AsyncIterator[str | ServerSentEvent]:
        parsed = self.parse_input(message)

        if isinstance(parsed, Command):
            it = self.eval_command(parsed)
        else:
            it = self.eval_message(message)

        try:
            async for msg in it:
                yield msg
        except KeyboardInterrupt:
            print("interrupt")
            self.client.clear_queue()

    def parse_input(self, message: str) -> str | Command:
        if not message.lstrip().startswith("!"):
            return message

        message = message.lstrip()[1:].strip()
        if len(message) == 0:
            raise ReplError('usage: "!op arg1 arg2 ..."')
        op, *args = shlex.split(message)
        return Command(op, args)

    async def eval_command(self, command: Command) -> AsyncIterator[str | ServerSentEvent]:
        try:
            ok = True
            async for msg in self.client.call_op(command.op, command.args):
                if msg.event == "error":
                    self.client.clear_queue()
                    logger.error(f"Command Error: {msg.data}")
                    ok = False
                    yield msg
            if ok:
                yield f"command {command} success"
        except SSEError as e:
            raise ReplError(str(e)) from e

    async def eval_message(self, message: str) -> AsyncIterator[ServerSentEvent]:
        try:
            async for msg in self.client.communicate(message):
                yield msg
        except SSEError as e:
            raise ReplError(str(e)) from e

    def print(self, msg: str | ServerSentEvent):
        if isinstance(msg, str):
            print(msg, flush=True)
            return

        assert isinstance(msg, ServerSentEvent), msg

        if msg.event == "content_block_delta":
            data = json.loads(msg.data)
            text = data["delta"]["text"]
            print(text.replace("\n\n", "\n"), end="", flush=True)
        elif msg.event == "content_block_stop":
            print(flush=True)
        elif msg.event == "error":
            e = SSEError(f"{self.client.addr}:{self.client.port}", msg.data)
            print(str(e), flush=True)
        else:
            logger.debug(f"unknown event: {msg}")

    async def repl(self):
        while True:
            try:
                # read
                message = self.read()
                if not message:
                    continue

                # eval
                stream = self.eval(message)

                # print
                async for msg in stream:
                    self.print(msg)

            except ReplError as e:
                print(f"Error: {e}")
                continue

            except KeyboardInterrupt:
                print("Ctrl+C pressed. closing...")
                return


async def amain():
    intp = ClaudeRepl(Client())
    async with intp.run():
        await intp.repl()


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
