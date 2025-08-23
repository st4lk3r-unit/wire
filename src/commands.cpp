#include <Arduino.h>

extern "C" {
  #ifndef KONSOLE_ENABLE_VT100
  #define KONSOLE_ENABLE_VT100 1
  #endif
  #ifndef KONSOLE_HISTORY
  #define KONSOLE_HISTORY 16
  #endif
  #ifndef KONSOLE_MAX_LINE
  #define KONSOLE_MAX_LINE 128
  #endif
  #ifndef KONSOLE_EOL_MODE
  #define KONSOLE_EOL_MODE 1
  #endif

  #include "konsole.h"
  #include "static.h"
}

#include "commands.h"
#include "wire.h"
#include "konsole.h"
#include "config.h"

void run_bidi_bridge();

int cmd_receive(struct konsole* ks, int, char**) {
  kon_printf(ks, "Entering RECEIVE mode (Serial1 -> USB). No further console output.\r\n");
  kon_printf(ks, "Wire: TX=%d RX=%d BAUD=%d. Power-cycle to exit.\r\n",
             WIRE_TX_PIN, WIRE_RX_PIN, WIRE_BAUD);
  Serial.flush();
  delay(50);
  run_bidi_bridge();
  return 0;
}

int cmd_send(struct konsole* ks, int, char**) {
  kon_printf(ks, "Entering SEND mode (USB -> Serial1). No further console output.\r\n");
  kon_printf(ks, "Wire: TX=%d RX=%d BAUD=%d. Power-cycle to exit.\r\n",
             WIRE_TX_PIN, WIRE_RX_PIN, WIRE_BAUD);
  Serial.flush();
  delay(50);
  run_bidi_bridge();
  return 0;
}
