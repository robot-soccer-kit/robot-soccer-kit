#include "bin_stream.h"
#include "shell.h"
#include <Arduino.h>
#include <stdio.h>

static uint32_t monitor_dt = 0;
static uint32_t monitor_last = 0;
static struct bin_stream_packet in = {0}, out = {0};

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
  } else {
    // Call user logic
    if (!bin_on_packet(in.type)) {
      bin_stream_ack(BIN_UNKNOWN_COMMAND);
    }
  }
}

void bin_stream_recv(uint8_t c) {
  switch (in.state) {
  case 0:
    if (c == BIN_STREAM_HEADER1) {
      in.state++;
    }
    break;
  case 1:
    if (c == BIN_STREAM_HEADER2) {
      in.state++;
    } else {
      in.state = 0;
    }
    break;
  case 2:
    in.type = c;
    in.state++;
    break;
  case 3:
    in.size = c;
    in.state++;
    if (c == 0) {
      in.state++;
    }
    in.checksum = 0;
    in.pointer = 0;
    if (in.size > BIN_STREAM_BUFFER) {
      in.state = 0;
    }
    break;
  case 4:
    in.buffer[in.pointer++] = c;
    in.checksum += c;
    if (in.pointer >= in.size) {
      in.state++;
    }
    break;
  case 5:
    in.state = 0;
    if (c == in.checksum) {
      in.pointer = 0;
      bin_stream_process();
    }
    break;
  }
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
  uint8_t k;
  bin_stream_send(BIN_STREAM_HEADER1);
  bin_stream_send(BIN_STREAM_HEADER2);
  bin_stream_send(out.type);
  bin_stream_send(out.size);
  for (k = 0; k < out.size; k++) {
    bin_stream_send(out.buffer[k]);
  }
  bin_stream_send(out.checksum);
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
