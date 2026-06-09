"""Hardware and transport adapters for the traffic signal model."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ESP32_UART_RX_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"


@dataclass(frozen=True)
class LightMapping:
    """ESP32-C3 transport settings for a signal light."""

    backend: str = "http"
    http_url: str = "http://192.168.4.1"
    serial_port: str | None = None
    serial_baud: int = 115200
    ble_name: str = "rgb-c3"
    ble_address: str | None = None
    esp32_brightness: float = 1.0
    esp32_color_order: str = "rbg"
    max_duty: int = 1023
    request_timeout: float = 2.0

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "LightMapping":
        backend = (
            environ.get("SIGNAL_LIGHT_BACKEND")
            or environ.get("SIGNAL_LIGHT_TRANSPORT")
            or _infer_backend(environ)
        )
        http_url = (
            environ.get("SIGNAL_LIGHT_HTTP_URL")
            or environ.get("SIGNAL_LIGHT_ESP32_URL")
            or "http://192.168.4.1"
        )
        return cls(
            backend=backend.strip().lower(),
            http_url=http_url.strip().rstrip("/") or "http://192.168.4.1",
            serial_port=_optional_env(environ, "SIGNAL_LIGHT_SERIAL_PORT"),
            serial_baud=_int_env(environ, "SIGNAL_LIGHT_SERIAL_BAUD", 115200),
            ble_name=environ.get("SIGNAL_LIGHT_BLE_NAME", "rgb-c3").strip() or "rgb-c3",
            ble_address=_optional_env(environ, "SIGNAL_LIGHT_BLE_ADDRESS"),
            esp32_brightness=_float_env(environ, "SIGNAL_LIGHT_ESP32_BRIGHTNESS", 1.0),
            esp32_color_order=_color_order_env(environ, "SIGNAL_LIGHT_ESP32_COLOR_ORDER", "rbg"),
            max_duty=_int_env(environ, "SIGNAL_LIGHT_MAX_DUTY", 1023),
            request_timeout=_float_env(environ, "SIGNAL_LIGHT_TIMEOUT", 2.0),
        )


class SignalLightError(RuntimeError):
    """Raised when the signal light hardware cannot be controlled."""


class _Driver(Protocol):
    def connect(self) -> None:
        ...

    def close(self) -> None:
        ...

    def write(self, *, green: bool = False, yellow: bool = False, red: bool = False) -> None:
        ...

    def write_brightness(self, *, green: float = 0.0, yellow: float = 0.0, red: float = 0.0) -> None:
        ...

    def off(self) -> None:
        ...


class SignalLight:
    """LightWriter-compatible facade for ESP32-C3 backends."""

    def __init__(self, mapping: LightMapping | None = None) -> None:
        self.mapping = mapping or LightMapping()
        self._driver: _Driver | None = None

    def __enter__(self) -> "SignalLight":
        self.connect()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def connect(self) -> None:
        if self._driver is not None:
            return
        self._driver = _build_driver(self.mapping)
        self._driver.connect()

    def close(self) -> None:
        if self._driver is None:
            return
        self._driver.close()
        self._driver = None

    def off(self) -> None:
        self.write(green=False, yellow=False, red=False)

    def write(self, *, green: bool = False, yellow: bool = False, red: bool = False) -> None:
        if self._driver is None:
            self.connect()
        assert self._driver is not None
        self._driver.write(green=green, yellow=yellow, red=red)

    def write_brightness(self, *, green: float = 0.0, yellow: float = 0.0, red: float = 0.0) -> None:
        if self._driver is None:
            self.connect()
        assert self._driver is not None
        self._driver.write_brightness(green=green, yellow=yellow, red=red)


class _ESP32CommandDriver:
    def __init__(self, mapping: LightMapping) -> None:
        self.mapping = mapping

    def connect(self) -> None:
        return

    def close(self) -> None:
        return

    def off(self) -> None:
        self.write()

    def write(self, *, green: bool = False, yellow: bool = False, red: bool = False) -> None:
        self.write_brightness(
            green=1.0 if green else 0.0,
            yellow=1.0 if yellow else 0.0,
            red=1.0 if red else 0.0,
        )

    def write_brightness(self, *, green: float = 0.0, yellow: float = 0.0, red: float = 0.0) -> None:
        color = _traffic_to_rgb(
            green=green,
            yellow=yellow,
            red=red,
            max_duty=self.mapping.max_duty,
            master_brightness=self.mapping.esp32_brightness,
            color_order=self.mapping.esp32_color_order,
        )
        power = any(value > 0 for value in color)
        command = {
            "cmd": "set",
            "power": power,
            "color": color,
            "blink_hz": 0,
            "brightness": 1.0,
        }
        self._send(command)

    def _send(self, command: dict[str, object]) -> None:
        raise NotImplementedError


class _HTTPESP32Driver(_ESP32CommandDriver):
    def _send(self, command: dict[str, object]) -> None:
        body = json.dumps(command, separators=(",", ":")).encode("utf-8")
        request = Request(
            self.mapping.http_url + "/api/control",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.mapping.request_timeout) as response:
                payload = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            raise SignalLightError(f"ESP32-C3 HTTP request failed: HTTP {exc.code}") from exc
        except URLError as exc:
            raise SignalLightError(f"ESP32-C3 HTTP request failed: {exc.reason}") from exc
        _raise_for_esp32_response(payload)


class _SerialESP32Driver(_ESP32CommandDriver):
    def __init__(self, mapping: LightMapping) -> None:
        super().__init__(mapping)
        self._serial = None

    def connect(self) -> None:
        if self._serial is not None:
            return
        if not self.mapping.serial_port:
            raise SignalLightError("SIGNAL_LIGHT_SERIAL_PORT is required when SIGNAL_LIGHT_BACKEND=serial.")
        try:
            import serial
        except ImportError as exc:
            raise SignalLightError("pyserial is not installed. Install pc-esp32-signal-light[serial].") from exc

        try:
            self._serial = serial.Serial(
                self.mapping.serial_port,
                self.mapping.serial_baud,
                timeout=self.mapping.request_timeout,
                write_timeout=self.mapping.request_timeout,
            )
        except Exception as exc:
            raise SignalLightError(f"Failed to open serial port {self.mapping.serial_port}: {exc}") from exc

    def close(self) -> None:
        if self._serial is None:
            return
        self._serial.close()
        self._serial = None

    def _send(self, command: dict[str, object]) -> None:
        if self._serial is None:
            self.connect()
        assert self._serial is not None
        line = json.dumps(command, separators=(",", ":")).encode("utf-8") + b"\n"
        try:
            self._serial.write(line)
            self._serial.flush()
            response = self._read_response()
        except Exception as exc:
            raise SignalLightError(f"ESP32-C3 serial write failed: {exc}") from exc
        if response:
            _raise_for_esp32_response(response)

    def _read_response(self) -> str:
        assert self._serial is not None
        deadline = time.monotonic() + self.mapping.request_timeout
        while time.monotonic() < deadline:
            line = self._serial.readline()
            if not line:
                continue
            text = line.decode("utf-8", errors="replace").strip()
            if text.startswith("{"):
                return text
        return ""


class _BLEESP32Driver(_ESP32CommandDriver):
    def __init__(self, mapping: LightMapping) -> None:
        super().__init__(mapping)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client = None

    def connect(self) -> None:
        if self._client is not None:
            return
        try:
            from bleak import BleakClient, BleakScanner
        except ImportError as exc:
            raise SignalLightError("bleak is not installed. Install pc-esp32-signal-light[ble].") from exc

        self._loop = asyncio.new_event_loop()
        try:
            address = self.mapping.ble_address
            if not address:
                address = self._loop.run_until_complete(_find_ble_address(BleakScanner, self.mapping.ble_name))
            client = BleakClient(address, timeout=self.mapping.request_timeout)
            self._loop.run_until_complete(client.connect())
        except Exception as exc:
            self.close()
            raise SignalLightError(f"Failed to connect BLE device {self.mapping.ble_name}: {exc}") from exc
        self._client = client

    def close(self) -> None:
        if self._loop is None:
            return
        try:
            if self._client is not None:
                self._loop.run_until_complete(self._client.disconnect())
        finally:
            self._client = None
            self._loop.close()
            self._loop = None

    def _send(self, command: dict[str, object]) -> None:
        if self._client is None:
            self.connect()
        assert self._client is not None
        assert self._loop is not None
        payload = json.dumps(command, separators=(",", ":")).encode("utf-8")
        try:
            self._loop.run_until_complete(
                self._client.write_gatt_char(ESP32_UART_RX_UUID, payload, response=True)
            )
        except Exception as exc:
            raise SignalLightError(f"ESP32-C3 BLE write failed: {exc}") from exc


async def _find_ble_address(scanner_cls: object, name: str) -> str:
    devices = await scanner_cls.discover(timeout=5.0)
    for device in devices:
        if getattr(device, "name", None) == name:
            return str(device.address)
    raise SignalLightError(f"BLE device named {name!r} was not found.")


def _build_driver(mapping: LightMapping) -> _Driver:
    if mapping.backend in {"http", "esp32-http"}:
        return _HTTPESP32Driver(mapping)
    if mapping.backend in {"serial", "uart", "esp32-serial"}:
        return _SerialESP32Driver(mapping)
    if mapping.backend in {"ble", "esp32-ble"}:
        return _BLEESP32Driver(mapping)
    raise SignalLightError("Unsupported SIGNAL_LIGHT_BACKEND. Use http, serial, or ble.")


def _traffic_to_rgb(
    *,
    green: float,
    yellow: float,
    red: float,
    max_duty: int,
    master_brightness: float,
    color_order: str = "rbg",
) -> list[int]:
    master = _clamp_float(master_brightness)
    red_input = _clamp_float(red)
    yellow_input = _clamp_float(yellow)
    green_input = _clamp_float(green)
    red_level = max(red_input, yellow_input) * master
    green_level = max(green_input, yellow_input) * master
    blue_level = min(red_input, yellow_input, green_input) * master
    levels = {"r": red_level, "g": green_level, "b": blue_level}
    return [int(round(levels[channel] * max_duty)) for channel in color_order]


def _raise_for_esp32_response(payload: str) -> None:
    if not payload.strip():
        return
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return
    if isinstance(parsed, dict) and parsed.get("ok") is False:
        raise SignalLightError(f"ESP32-C3 rejected command: {parsed.get('error', parsed)}")


def _infer_backend(environ: Mapping[str, str]) -> str:
    if environ.get("SIGNAL_LIGHT_HTTP_URL") or environ.get("SIGNAL_LIGHT_ESP32_URL"):
        return "http"
    if environ.get("SIGNAL_LIGHT_SERIAL_PORT"):
        return "serial"
    if environ.get("SIGNAL_LIGHT_BLE_ADDRESS") or environ.get("SIGNAL_LIGHT_BLE_NAME"):
        return "ble"
    return "http"


def _optional_env(environ: Mapping[str, str], key: str) -> str | None:
    value = environ.get(key)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _int_env(environ: Mapping[str, str], key: str, default: int) -> int:
    try:
        return int(environ.get(key, str(default)))
    except ValueError:
        return default


def _float_env(environ: Mapping[str, str], key: str, default: float) -> float:
    try:
        return float(environ.get(key, str(default)))
    except ValueError:
        return default


def _color_order_env(environ: Mapping[str, str], key: str, default: str) -> str:
    value = environ.get(key, default).strip().lower()
    if sorted(value) != ["b", "g", "r"]:
        return default
    return value


def _clamp_float(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
