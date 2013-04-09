#ifndef ROLLSUM_H
#define ROLLSUM_H

#include "stdint.h"
#include "circularbuffer.h"

typedef struct _Rollsum {
  unsigned long count;               /* count of bytes included in sum */
  unsigned long s1;                  /* s1 part of sum */
  unsigned long s2;                  /* s2 part of sum */
} Rollsum;

typedef struct _RollingState {
  Rollsum sum;
  CircularBuffer* cb;
} RollingState;

RollingState* create_rolling(uint32_t window_size);
int is_full(RollingState* state);
int is_empty(RollingState* state);
void push_rolling(RollingState* state, unsigned char c_add);
void push_buffer_rolling(RollingState* state, const char* buf, unsigned len);
unsigned value_rolling(RollingState* state);
uint64_t value64_rolling(RollingState* state);
void destroy_rolling(RollingState* state);

#endif
