# Z-Control Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Home Assistant custom integration for [Zoeller Z-Control](https://www.zoeller.com/) sump pump alarm systems.

This integration connects to the Z-Control cloud service (zcontrolcloud.com) to monitor your sump pump alarm status.

## Features

- **Binary Sensors**: Monitor alarm states
  - Online status (device connectivity)
  - Input 1 (water detection)
  - Input 2
  - AC Power fault
  - Battery fault

- **Sensors**: Device information
  - WiFi signal strength
  - Alarm count
  - Last heartbeat timestamp
  - Firmware version

- **Buttons**: Device controls
  - Silence Alarm
  - Reset Device

## Requirements

- A Zoeller Z-Control compatible device (e.g., APak alarm system)
- An account at [zcontrolcloud.com](https://account.zcontrolcloud.com)
- Home Assistant 2024.11 or newer

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add this repository URL and select "Integration" as the category
5. Click "Add"
6. Search for "Z-Control" and install it
7. Restart Home Assistant

### Manual Installation

1. Download the `custom_components/zcontrol` folder from this repository
2. Copy it to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Z-Control"
4. Enter your zcontrolcloud.com email and password
5. Your device(s) will be automatically discovered

Devices added to your Z-Control account later are discovered during normal
polling, without reloading the integration. Entity unique IDs are unchanged;
devices that temporarily disappear become unavailable and reuse their existing
entities when they return.

### Account timezone

Heartbeat timestamps may include an explicit UTC offset, which is preserved.
Timestamps without an offset use Home Assistant's timezone by default. If your
Z-Control account uses a different timezone, open the integration's **Configure**
options and enter the account's IANA timezone (for example, `America/Chicago`).
Saving a changed timezone reloads the integration. This changes timestamp
interpretation in Home Assistant; it does not change settings on Z-Control or
the physical device. A timestamp without an offset remains ambiguous during a
repeated hour at the end of daylight saving time.

## Entities

After setup, the following entities are created for each device:

| Entity | Type | Description |
|--------|------|-------------|
| `binary_sensor.*_online` | Binary Sensor | Device connectivity status |
| `binary_sensor.*_input_1` | Binary Sensor | Input 1 alarm (water detected) |
| `binary_sensor.*_input_2` | Binary Sensor | Input 2 alarm |
| `binary_sensor.*_ac_power` | Binary Sensor | AC power fault |
| `binary_sensor.*_battery` | Binary Sensor | Battery fault |
| `sensor.*_wifi_signal` | Sensor | WiFi signal strength (dBm) |
| `sensor.*_alarm_count` | Sensor | Number of active alarms; unknown if the field is missing |
| `sensor.*_last_heartbeat` | Sensor | Last device check-in time |
| `sensor.*_firmware` | Sensor | Firmware version (disabled by default) |
| `button.*_silence_alarm` | Button | Silence the active alarm |
| `button.*_reset_device` | Button | Reset the device |

## Troubleshooting

### Check Logs
Go to **Settings** → **System** → **Logs** and search for "zcontrol" to see any error messages.

### Enable Debug Logging
Add this to your `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.zcontrol: debug
```

### Temporary connection failures

A network/API failure, including one during automatic reauthentication, leaves
the integration unavailable and retries at the next polling interval. It does
not request new credentials. An actual authentication failure starts Home
Assistant's reauthentication flow. Failed setup attempts close their HTTP session
before Home Assistant retries.

### Authentication Issues
If you get authentication errors, verify:
1. Your email and password work at [zcontrolcloud.com](https://account.zcontrolcloud.com)
2. Your account is active and not locked

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

With Home Assistant 2024.11 or newer, pytest, and pytest-asyncio installed, run:

```sh
python -m pytest -q
python -m compileall -q custom_components tests
```

The tests cover session cleanup, update errors, alarm-count missing data,
heartbeat formats and timezones, config/reauth/options flows, and entity discovery.
A simulated-cloud integration test runs real Home Assistant platform setup,
options reload, and unload. No live cloud credentials or device commands are used.

## Disclaimer

This integration is not affiliated with or endorsed by Zoeller Company. Use at your own risk.

## License

MIT License - see [LICENSE](LICENSE) file for details.
