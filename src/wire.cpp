#include "Arduino.h"
#include "config.h"

// one-time init for the inter-ESP UART
static bool wire_inited = false;

static inline size_t write_chunk(HardwareSerial& s, const uint8_t* p, size_t n) {
  // never try to shove more than what's available, cap to 256/512 to avoid big bursts
  size_t room = s.availableForWrite();
  size_t send = n;
  if (room && send > room) send = room;
  if (send > 256) send = 256;
  return s.write(p, send);
}

void wire_init() {
  if (wire_inited) return;
  // Start USB console in your main setup() (Serial.begin(...))
  // Start wire UART here with large buffers
  constexpr int WIRE_RXBUF = 32768;
  Serial1.begin(WIRE_BAUD, SERIAL_8N1, WIRE_RX_PIN, WIRE_TX_PIN, false, WIRE_RXBUF);

  Serial1.setRxBufferSize(32768);
  Serial1.setTxBufferSize(32768);
  Serial.setRxBufferSize(32768);
  Serial.setTxBufferSize(32768);
  wire_inited = true;
}


void run_receive_bridge() {
  wire_init();
  static uint8_t buf[BRIDGE_BUF_SZ];
  for (;;) {
    size_t n = Serial1.available();
    if (n) {
      if (n > sizeof(buf)) n = sizeof(buf);
      n = Serial1.readBytes(buf, n);
      size_t off = 0;
      while (off < n) off += Serial.write(buf + off, n - off);
      Serial.flush(false);
    }
    delay(0);
  }
}

void run_send_bridge() {
  wire_init();
  static uint8_t buf[BRIDGE_BUF_SZ];
  for (;;) {
    size_t n = Serial.available();
    if (n) {
      if (n > sizeof(buf)) n = sizeof(buf);
      n = Serial.readBytes(buf, n);
      size_t off = 0;
      while (off < n) off += Serial1.write(buf + off, n - off);
      Serial1.flush(false);
    }
    delay(0);
  }
}

void run_bidi_bridge() {
  wire_init();

  static uint8_t buf_wire_to_usb[BRIDGE_BUF_SZ];
  static uint8_t buf_usb_to_wire[BRIDGE_BUF_SZ];

  for (;;) {
    size_t a = Serial1.available();
    if (a) {
      if (a > sizeof(buf_wire_to_usb)) a = sizeof(buf_wire_to_usb);
      a = Serial1.readBytes(buf_wire_to_usb, a);
      size_t off = 0;
      while (off < a) off += Serial.write(buf_wire_to_usb + off, a - off);
      Serial.flush(false);
    }

    size_t b = Serial.available();
    if (b) {
      if (b > sizeof(buf_usb_to_wire)) b = sizeof(buf_usb_to_wire);
      b = Serial.readBytes(buf_usb_to_wire, b);
      size_t off = 0;
      while (off < b) off += Serial1.write(buf_usb_to_wire + off, b - off);
      Serial1.flush(false);
    }

    delay(0);
  }
}