#include "bin_stream.h"
#include "shell.h"
#include <Arduino.h>
#include <stdio.h>

static uint8_t id = 255;
static uint32_t monitor_dt = 0;
static uint8_t has_address = 0;
static unsigned long monitor_last = 0;
static struct bin_stream_packet in = {0}, out = {0};

void bin_stream_enable_address(uint8_t enable) { has_address = enable; }

void bin_stream_set_id(uint8_t id_) { id = id_; }

void bin_stream_set_monitor_period(uint32_t period) { monitor_dt = period; }

void bin_stream_ack(int code) {
  if (code != BIN_NO_ACK) {
    bin_stream_begin(BIN_STREAM_ACK);
    bin_stream_append(code);
    bin_stream_end();
  }
}

void bin_stream_process() {
  if (in.type == BIN_STREAM_MONITOR) {
    uint8_t frequency = bin_stream_read_int();
    if (frequency == 0) {
      monitor_dt = 0;
    } else {
      monitor_dt = (1000 / frequency);
      if (monitor_dt < 10) {
        monitor_dt = 10;
      }
    }
    bin_on_monitor();
  } else if (in.type == BIN_STREAM_HEARTBEAT) {
    // This packet type has no effect
  } else {
    // Call user logic
    if (!bin_on_packet(in.type)) {
      bin_stream_ack(BIN_UNKNOWN_COMMAND);
    }
  }
}

bool bin_stream_recv(uint8_t c) {
  int STATE_HEADER1 = 0;
  int STATE_HEADER2 = 1;
  int STATE_DEST = 2;
  int STATE_TYPE = 3;
  int STATE_SIZE = 4;
  int STATE_DATA = 5;
  int STATE_CHECKSUM = 6;

  if (!has_address) {
    // Disabling address reception
    STATE_DEST = -1;
    STATE_TYPE -= 1;
    STATE_SIZE -= 1;
    STATE_DATA -= 1;
    STATE_CHECKSUM -= 1;
  }

  if (in.state == STATE_HEADER1) {
    if (c == BIN_STREAM_HEADER1) {
      in.state++;
    }
  } else if (in.state == STATE_HEADER2) {
    if (c == BIN_STREAM_HEADER2) {
      in.state++;
    } else {
      in.state = STATE_HEADER1;
    }
  } else if (in.state == STATE_DEST) {
    in.dest = c;
    in.state++;
  } else if (in.state == STATE_TYPE) {
    in.type = c;
    in.state++;
  } else if (in.state == STATE_SIZE) {
    in.size = c;
    in.state++;
    if (c == 0) {
      in.state++;
    }
    in.checksum = 0;
    in.pointer = 0;
    if (in.size > BIN_STREAM_BUFFER) {
      in.state = STATE_HEADER1;
    }
  } else if (in.state == STATE_DATA) {
    in.buffer[in.pointer++] = c;
    in.checksum += c;
    if (in.pointer >= in.size) {
      in.state++;
    }
  } else if (in.state == STATE_CHECKSUM) {
    in.state = STATE_HEADER1;
    if (c == in.checksum) {
      in.pointer = 0;

      if (has_address && in.dest != id) {
        return false;
      }

      bin_stream_process();
      return true;
    }
  } else {
    // This is not supposed to happen, go back to initial state
    in.state = STATE_HEADER1;
  }

  return false;
}

void bin_stream_begin(uint8_t type_) {
  out.size = 0;
  out.checksum = 0;
  out.type = type_;
}

void bin_stream_append(uint8_t c) {
  if (out.size < BIN_STREAM_BUFFER) {
    out.checksum += c;
    out.buffer[out.size++] = c;
  }
}

void bin_stream_append_int(int32_t i) {
  bin_stream_append((i >> 24) & 0xff);
  bin_stream_append((i >> 16) & 0xff);
  bin_stream_append((i >> 8) & 0xff);
  bin_stream_append((i >> 0) & 0xff);
}

void bin_stream_append_short(uint16_t s) {
  bin_stream_append((s >> 8) & 0xff);
  bin_stream_append((s >> 0) & 0xff);
}

void bin_stream_append_value(uint32_t value) {
  bin_stream_append((value >> 24) & 0xff);
  bin_stream_append((value >> 16) & 0xff);
  bin_stream_append((value >> 8) & 0xff);
  bin_stream_append((value >> 0) & 0xff);
}

void bin_stream_end() {
  uint8_t packet[out.size + 6];
  uint8_t i = 0;

  packet[i++] = BIN_STREAM_HEADER1;
  packet[i++] = BIN_STREAM_HEADER2;
  if (has_address) {
    packet[i++] = 0;
  }
  packet[i++] = out.type;
  packet[i++] = out.size;

  for (uint8_t k = 0; k < out.size; k++) {
    packet[i++] = out.buffer[k];
  }
  packet[i++] = out.checksum;

  bin_stream_send(packet, i);
}

void bin_stream_tick() {
  if (monitor_dt > 0) {
    if ((millis() - monitor_last) > monitor_dt) {
      monitor_last = millis();
      bin_on_monitor();
    }
  }
}

uint8_t bin_stream_read() {
  if (in.pointer < BIN_STREAM_BUFFER) {
    return in.buffer[in.pointer++];
  } else {
    return 0;
  }
}

uint16_t bin_stream_read_short() {
  uint16_t i = 0;
  i |= bin_stream_read() << 8;
  i |= bin_stream_read() << 0;

  return i;
}

uint32_t bin_stream_read_int() {
  uint32_t i = 0;
  i |= bin_stream_read() << 24;
  i |= bin_stream_read() << 16;
  i |= bin_stream_read() << 8;
  i |= bin_stream_read() << 0;

  return i;
}

uint8_t *bin_stream_data() { return &in.buffer[in.pointer]; }

uint8_t bin_stream_available() { return in.size - in.pointer; }
