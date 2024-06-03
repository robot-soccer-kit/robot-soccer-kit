#ifndef _RHOCK_STREAM_H
#define _RHOCK_STREAM_H

#include "config.h"
#include <stddef.h>
#include <stdint.h>

// Packet heades
#define BIN_STREAM_HEADER1 0xff
#define BIN_STREAM_HEADER2 0xaa

// Packet types
#define BIN_STREAM_ACK 0x00
#define BIN_STREAM_MONITOR 0x01
#define BIN_STREAM_STORE 0x02
#define BIN_STREAM_PROGRAM 0x03
#define BIN_STREAM_PRINT 0x04
#define BIN_STREAM_USER 0x05
#define BIN_STREAM_RESET 0x06
#define BIN_STREAM_HEARTBEAT 0x07

// Errors
#define BIN_OK 0
#define BIN_STORE_ALLOC_ERR 1
#define BIN_STORE_CHUNK_ERR 2
#define BIN_STORE_LOAD_ERR 3
#define BIN_UNKNOWN_COMMAND 4
#define BIN_PROGRAM_ERROR 5
#define BIN_NO_ACK 0xff

#define BIN_STREAM_BUFFER 128

struct bin_stream_packet {
  uint8_t dest;
  uint8_t state;
  uint8_t buffer[BIN_STREAM_BUFFER];
  uint8_t size;
  uint8_t checksum;
  uint8_t type;
  uint8_t pointer;
};

// Abstraction layer
bool bin_stream_recv(uint8_t c);                           // To call
extern void bin_stream_send(uint8_t *packet, size_t size); // To implement
extern char bin_on_packet(uint8_t type);                   // To implment
extern void bin_on_monitor();                              // To implement

void bin_stream_set_monitor_period(uint32_t period);
void bin_stream_begin(uint8_t type);
void bin_stream_append(uint8_t c);
void bin_stream_append_int(int32_t i);
void bin_stream_append_short(uint16_t s);
void bin_stream_append_value(uint32_t value);
void bin_stream_end();
void bin_stream_tick();
void bin_stream_set_id(uint8_t id);

uint8_t *bin_stream_data();
uint8_t bin_stream_available();
uint8_t bin_stream_read();
uint16_t bin_stream_read_short();
uint32_t bin_stream_read_int();

void bin_stream_ack(int code);
void bin_stream_enable_address(uint8_t enable);

#endif
