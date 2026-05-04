# Canvas Display — Home Assistant Integration

> ⚠️ **Early Development** — This integration is under active development. Expect breaking changes between releases. Not recommended for production use.

HACS integration for [Canvas Display](https://github.com/bushrangerlabs/canvas-display) — a customizable canvas-based display system for kiosk devices and single-board computers.

## Features

- **Status sensor** — `online` / `offline` per device
- **Active page select** — switch the displayed page directly from HA
- **Multiple devices** — add one integration entry per Canvas Display device

## Requirements

- [Canvas Display](https://github.com/bushrangerlabs/canvas-display) server running and reachable from HA (default port `3100`)

## Installation

1. In HACS, add `bushrangerlabs/canvas-display-hacs` as a custom repository (type: **Integration**)
2. Download **Canvas Display** from HACS
3. Restart Home Assistant
4. **Settings → Devices & Services → Add Integration → Canvas Display**
5. Enter the server URL for each device, e.g. `http://192.168.1.x:3100`

## Entities

Each device gets:

| Entity | Type | Description |
|---|---|---|
| `sensor.{device_name}_server_status` | Sensor | `online` or `offline` |
| `select.{device_name}_active_page` | Select | Switch the active display page |
