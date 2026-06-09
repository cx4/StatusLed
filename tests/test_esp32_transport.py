from signal_light.hardware import LightMapping, SignalLight, _HTTPESP32Driver, _traffic_to_rgb


def test_traffic_light_colors_map_to_esp32_rgb() -> None:
    assert _traffic_to_rgb(green=1, yellow=0, red=0, max_duty=1023, master_brightness=1) == [0, 0, 1023]
    assert _traffic_to_rgb(green=0, yellow=1, red=0, max_duty=1023, master_brightness=1) == [1023, 0, 1023]
    assert _traffic_to_rgb(green=0, yellow=0, red=1, max_duty=1023, master_brightness=1) == [1023, 0, 0]
    assert _traffic_to_rgb(green=1, yellow=1, red=1, max_duty=1023, master_brightness=1) == [1023, 1023, 1023]


def test_traffic_light_brightness_scales_esp32_rgb() -> None:
    assert _traffic_to_rgb(green=0.5, yellow=0, red=0, max_duty=1023, master_brightness=0.5) == [0, 0, 256]


def test_traffic_light_color_order_can_use_standard_rgb() -> None:
    assert _traffic_to_rgb(
        green=1,
        yellow=0,
        red=0,
        max_duty=1023,
        master_brightness=1,
        color_order="rgb",
    ) == [0, 1023, 0]


def test_mapping_infers_http_backend_from_url() -> None:
    mapping = LightMapping.from_env({"SIGNAL_LIGHT_HTTP_URL": "http://192.168.4.1/"})

    assert mapping.backend == "http"
    assert mapping.http_url == "http://192.168.4.1"
    assert mapping.esp32_color_order == "rbg"


def test_mapping_accepts_esp32_color_order_from_env() -> None:
    mapping = LightMapping.from_env(
        {
            "SIGNAL_LIGHT_HTTP_URL": "http://192.168.4.1/",
            "SIGNAL_LIGHT_ESP32_COLOR_ORDER": "rgb",
        }
    )

    assert mapping.esp32_color_order == "rgb"


def test_http_backend_sends_esp32_command(monkeypatch) -> None:
    sent: list[dict[str, object]] = []
    monkeypatch.setattr(_HTTPESP32Driver, "_send", lambda self, command: sent.append(command))

    light = SignalLight(LightMapping(backend="http"))
    light.write(yellow=True)

    assert sent == [
        {
            "cmd": "set",
            "power": True,
            "color": [1023, 0, 1023],
            "blink_hz": 0,
            "brightness": 1.0,
        }
    ]
