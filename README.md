# WIRE

WIRE provides a minimal and verifiable way to move data between two endpoints without relying on network infrastructure.  
Two ESP32 boards are used as a physical UART bridge between two laptops. This allows key material or files to be exchanged face-to-face without producing any network trace.


## Purpose

The objective is to enable file or key exchange in an environment where any form of wireless or wired network traffic could be monitored or logged.  
Instead of transmitting over IP, two operators meet, connect ESP32 devices cross-wired on GPIO pins, and transfer the payload via a controlled point-to-point link.  
The only observable activity is power and serial traffic on the devices.


## Operation Concept

- Each ESP32 runs the `wire` firmware, exposing a serial console over USB.  
- Commands are available on the console:
  - `send` – starts bridge mode to transmit host USB input out of GPIO TX.
  - `receive` – starts bridge mode to read from GPIO RX and forward to host USB.
- When `send` or `receive` mode is active the ESP acts as a transparent bridge.  
- Two laptops run `examples_wrapper.py`. One side initiates `--send`, the other `--receive`.  
- Data is encapsulated in a simple reliable protocol:
  - Handshake (`HS20`) with filename, size, and CRC32.
  - Session header (`WRP2`).
  - Data sent in blocks with per-block CRC and ACK/NAK.
  - Final CRC verification on receiver before file is finalized.


## Hardware Connections

- Default pins: `TX=GPIO18`, `RX=GPIO19`.  
- Cross-connect TX to RX and RX to TX.  
- Tie grounds together.  
- No other connections are required.  
- Default UART baud rate on the wire link: `115200`. Adjustable in `config.h`.

```

Laptop A ←USB→ ESP32 A ←TX/RX→ ESP32 B ←USB→ Laptop B

```


## Repository Layout

```

src/
main.cpp        - console initialization
commands.cpp    - command handlers (send, receive, etc.)
wire.cpp/.h     - bridge implementation
config.h        - configuration (pins, baud, buffer sizes)
examples\_wrapper.py - Python3 transfer tool
README.md

```


## Building Firmware

Build and flash with PlatformIO:

```

pio run -t upload

```

Configuration is in `config.h`. Adjust TX/RX pins, baud rate, and buffer size as required.


## Usage

### Start Receiver

On the host connected to the ESP32 that will receive data:

```

python3 examples\_wrapper.py --receive \
--port /dev/ttyUSB0 \
--usb-baud 115200 \
--output received.txt

```

### Start Sender

On the host connected to the ESP32 that will send data:

```

python3 examples\_wrapper.py --send \
--port /dev/ttyUSB1 \
--usb-baud 115200 \
--file payload.txt

```

### Output

- By default:
  - Sender prints percentage and blocks sent.
  - Receiver prints a line each time a frame is accepted.
- With `-v`:
  - Both sides print per-block ACK/NAK, throughput, packets per second, and estimated time remaining.


## Protocol

- **Handshake**
  - Magic: `HS20`
  - Version: 1 byte
  - Filename length: 2 bytes
  - Total length: 8 bytes
  - File CRC32: 4 bytes
  - Filename
- **Session header**
  - Magic: `WRP2`
  - Version: 1 byte
  - Total length: 8 bytes
  - File CRC32: 4 bytes
- **Block**
  - Sequence: 2 bytes
  - Length: 2 bytes
  - Data
  - Block CRC32: 4 bytes
- **Control**
  - `K` – ACK
  - `N` – NAK
  - `OK` – final CRC success
  - `NO` – final CRC fail


## Notes

- Default USB console baud: `115200`. Must match `--usb-baud` in the wrapper.  
- Wire link baud (`WIRE_BAUD`) can be increased if both ESPs and cabling are stable.  
- If a transfer fails, the `.part` file remains for inspection.  
- The protocol ensures that data either arrives intact (CRC-verified) or is rejected.
