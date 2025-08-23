#pragma once
#include <Arduino.h>
#include "config.h"

// Initialize the ESP<->ESP UART (Serial1) with defined pins/baud.
void wire_init();

// Blocking run loops; never return. Power-cycle or reset to exit.
void run_receive_bridge();
void run_send_bridge();
void run_bidi_bridge();
