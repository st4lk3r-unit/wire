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
#include "config.h"

static struct konsole        g_ks;
static struct kon_line_state g_line;

extern "C" void kon_debug_rxdump(int on);

void setup() {
  Serial.begin(WIRE_BAUD);
  Serial.setRxBufferSize(32768);
  Serial.setTxBufferSize(32768);
  while (!Serial) { delay(10); }

  konsole_io io = {
    [](void*) -> size_t { return (size_t)Serial.available(); },
    [](void*, uint8_t* b, size_t n) -> size_t {
      size_t i = 0; while (i < n && Serial.available()) b[i++] = (uint8_t)Serial.read();
      return i;
    },
    [](void*, const uint8_t* b, size_t n) -> size_t { return (size_t)Serial.write(b, n); },
    [](void*) -> uint32_t { return (uint32_t)millis(); },
    nullptr
  };

  static const kon_cmd g_cmds[] = {
    {"receive", "bridge Serial1->USB (raw)", cmd_receive},
    {"send",    "bridge USB->Serial1 (raw)", cmd_send},
  };

  konsole_init(&g_ks, &io, g_cmds, sizeof(g_cmds)/sizeof(g_cmds[0]), "# ", true);
  g_ks.line = &g_line;
  konsole_set_mode(&g_ks, KON_MODE_ANSI);

  kon_debug_rxdump(0);

  kon_banner(&g_ks, "WIRE - UART Bridge");
  Serial.flush();
}

void loop() {
  konsole_poll(&g_ks);
}