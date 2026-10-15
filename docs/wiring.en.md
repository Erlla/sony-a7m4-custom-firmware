# Custom flashing cable

[中文](wiring.md) · [Back](../README.en.md)

You need an RP2040-Zero, a correctly wired Sony Multi-port breakout, conductors, a verified electrical interface and USB connections to the PC. Camera USB carries fastboot; RP2040 USB carries the boot bridge protocol.

| RP2040 GPIO | Camera signal | Direction |
|---|---|---|
| GP28 | Multi RX | RP2040 → camera boot data |
| GP29 | Multi TX | Camera → RP2040 boot status |
| GP27 | RESET | Reset control |
| GND | GND | Common ground |

**GPIO numbers are not camera connector pin numbers.** Verify physical pin locations, orientation and viewing side using the upstream [Multi pinout](https://github.com/DavidBuchanan314/ILCE-7M4-RE/blob/main/images/multi_pinout.png) and [breakout photograph](https://github.com/DavidBuchanan314/ILCE-7M4-RE/blob/main/images/multi_breakout.jpg). Do not infer pin numbers from wire colors.

The camera interface is approximately 1.8 V; RP2040 is a 3.3 V device. The upstream bridge defaults to `OPEN_DRAIN`, which pulls low or releases the line to the target pull-up. This does not automatically prove voltage compatibility in both directions. Check pull-ups, actual voltages, receiver thresholds, RESET wiring and the bridge board; use suitable level translation where necessary. Never connect 3.3 V/5 V push-pull outputs directly to camera signals or inject power based on this signal table.

With the camera disconnected, check continuity, shorts, ground and orientation first. Verify the bridge electrical behavior before attachment. A connector fitting mechanically says nothing about its pinout.

The bridge transmits BootROM records to SRAM; a camera payload then starts USB fastboot. The host receives startup status only and does not expose an interactive UART console. Serial boot wiring remains necessary for this fastboot entry method.

The upstream default board is `rp2040:rp2040:waveshare_rp2040_zero`, built with `-DOPEN_DRAIN`; `UART_TX` is not needed. Hold BOOTSEL while connecting the bridge USB for initial firmware installation. Read [risks/backups](../README.en.md) and [setup](setup.en.md) before operating real hardware.
