import asyncio
import logging
import re

from asyncio import StreamReader, StreamWriter, sleep
from asyncio.exceptions import TimeoutError
from enum import Enum

logger = logging.getLogger(__name__)
error_regexp = re.compile("E[0-9]{2}")


class DeviceType(Enum):
    SURROUND_SOUND_PROCESSOR = "surround_sound_processor"
    HDMI_SWITCHER = "hdmi_switcher"
    UNKNOWN = "unknown"


class AuthenticationError(Exception):
    pass


class ResponseError(Exception):
    pass


def is_error_response(response: str) -> bool:
    return error_regexp.match(response) is not None


class ExtronDevice:
    def __init__(self, host: str, port: int, password: str) -> None:
        self._host = host
        self._port = port
        self._password = password
        self._reader: StreamReader | None = None
        self._writer: StreamWriter | None = None
        self._semaphore = asyncio.Semaphore()
        self._connected = False

    async def _read_until(self, phrase: str) -> str | None:
        b = bytearray()

        while not self._reader.at_eof():
            byte = await self._reader.read(1)
            b += byte

            if b.endswith(phrase.encode()):
                return b.decode()

        return None

    async def attempt_login(self):
        return

    async def connect(self):
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)

        try:
            await asyncio.wait_for(self.attempt_login(), timeout=5)
            self._connected = True
            logger.info(f"Connected and authenticated to {self._host}:{self._port}")
        except TimeoutError:
            raise AuthenticationError()

    async def disconnect(self):
        self._connected = False

        # Ignore potential connection errors here, we're about to disconnect after all
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except ConnectionError:
            pass

    async def reconnect(self):
        await self.disconnect()
        await self.connect()

    def is_connected(self) -> bool:
        return self._connected

    async def _run_command_internal(self, command: str):
        async with self._semaphore:
            self._writer.write(f"{command}\n".encode())
            await self._writer.drain()

            return await self._read_until("\r\n")

    async def run_command(self, command: str) -> str:
        try:
            response = await asyncio.wait_for(self._run_command_internal(command), timeout=3)

            if response is None:
                raise RuntimeError("Command failed")

            if is_error_response(response):
                # If response is E10, retry up to 5 times
                if response == "E10":
                    count = 0
                    while count < 5:
                        await sleep(1)
                        response = await asyncio.wait_for(self._run_command_internal(command), timeout=3)
                        if is_error_response(response) and response == "E10":
                            count+=1
                        else:
                            break
                else:
                    raise ResponseError(f"Command failed with error code {response}")

            return response.strip()
        except TimeoutError:
            raise RuntimeError("Command timed out")
        except (ConnectionResetError, BrokenPipeError):
            self._connected = False
            raise RuntimeError("Connection was reset")
        finally:
            if not self._connected:
                logger.warning("Connection seems to be broken, will attempt to reconnect")
                await self.reconnect()

    async def query_model_name(self):
        return await self.run_command("1I")

    async def query_firmware_version(self):
        return await self.run_command("Q")

    async def query_part_number(self):
        return await self.run_command("N")

    async def reboot(self):
        await self.run_command("\x1b" + "1BOOT")


class SurroundSoundProcessor:
    def __init__(self, device: ExtronDevice) -> None:
        self._device = device

    def get_device(self) -> ExtronDevice:
        return self._device

    async def view_input(self) -> int:
        return int((await self._device.run_command("$"))[3:])

    async def select_input(self, input: int):
        await self._device.run_command(f"{str(input)}$")

    async def mute(self):
        await self._device.run_command("1Z")

    async def unmute(self):
        await self._device.run_command("0Z")

    async def is_muted(self) -> bool:
        is_muted = await self._device.run_command("Z")
        return is_muted == "Amt1"

    async def get_volume_level(self):
        volume = await self._device.run_command("V")
        return int(volume[3:])

    async def set_volume_level(self, level: int):
        await self._device.run_command(f"{level}V")

    async def increment_volume(self):
        await self._device.run_command("+V")

    async def decrement_volume(self):
        await self._device.run_command("-V")

    async def get_temperature(self) -> int:
        temperature = await self._device.run_command("20S")
        return int(temperature[6:])


class HDMISwitcher:
    def __init__(self, device: ExtronDevice) -> None:
        self._device = device

    def get_device(self) -> ExtronDevice:
        return self._device

    async def view_input(self) -> int:
        return int(await self._device.run_command("!"))

    async def select_input(self, input: int):
        await self._device.run_command(f"{str(input)}!")
