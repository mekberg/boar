#ifndef CIRCULARBUFFER_H
#define CIRCULARBUFFER_H

#include "stdint.h"

typedef struct _CircularBuffer {
  uint32_t magic;
  uint32_t circular_buffer_size; // Circular buffer size
  uint32_t physical_buffer_size; // Actual size of the physical buffer
  uint32_t pos; // Current start position in the physical buffer
  uint32_t length; // The number of stored bytes in the circular buffer
  char* buf; // buffer
  uint32_t sentinel;
} CircularBuffer;

void print_circular_buffer(CircularBuffer* state);
CircularBuffer* create_circular_buffer(uint32_t window_size);
void destroy_circular_buffer(CircularBuffer* state);
void push_circular_buffer(CircularBuffer* state, char c);
char rotate_circular_buffer(CircularBuffer* state, const char c);
char get_circular_buffer(CircularBuffer* state, const uint32_t pos);
void print_circular_buffer(CircularBuffer* state);
int is_full_circular_buffer(CircularBuffer* state);

#endif
