#pragma once

// UART link (ESP-to-ESP) configuration
#ifndef WIRE_TX_PIN
#define WIRE_TX_PIN 18
#endif

#ifndef WIRE_RX_PIN
#define WIRE_RX_PIN 19
#endif

#ifndef WIRE_BAUD
// Default baudrate; adjust as needed (e.g., 2000000 for 2 Mbps)
#define WIRE_BAUD 115200
#endif

// Bridge I/O buffer size
#ifndef BRIDGE_BUF_SZ
#define BRIDGE_BUF_SZ 32768
#endif
