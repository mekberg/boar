// Copyright 2013 Mats Ekberg
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#ifndef CIRCULARBUFFER_H
#define CIRCULARBUFFER_H

#include "stdint.h"

// A fixed-size ring buffer holding the last "circular_buffer_size"
// bytes. The rolling checksum only ever needs the byte that is about
// to leave the window, so the buffer is exactly window-sized and the
// hot operations are branch-light, inlinable, and allocation-free.
typedef struct _CircularBuffer {
  uint32_t magic;
  uint32_t circular_buffer_size; // Window size == physical buffer size
  uint32_t pos; // Index of the oldest byte (the next one to leave the window)
  uint32_t length; // Number of bytes currently stored (<= circular_buffer_size)
  char* buf; // Physical buffer of "circular_buffer_size" bytes
  uint32_t sentinel;
} CircularBuffer;

CircularBuffer* create_circular_buffer(uint32_t window_size);
void destroy_circular_buffer(CircularBuffer* state);
void print_circular_buffer(CircularBuffer* state);

static inline int is_full_circular_buffer(const CircularBuffer* const state){
  return state->length == state->circular_buffer_size;
}

// Append a byte to a buffer that is known not to be full yet. While
// the buffer is filling, "pos" is still 0, so the next free slot is
// simply at index "length".
static inline void push_circular_buffer(CircularBuffer* const state, const char c) {
  state->buf[state->length] = c;
  state->length += 1;
}

// Overwrite the oldest byte with "c" and return the byte that left
// the window. Only valid on a full buffer.
static inline char rotate_circular_buffer(CircularBuffer* const state, const char c) {
  const uint32_t pos = state->pos;
  const char pushed_out = state->buf[pos];
  state->buf[pos] = c;
  uint32_t next = pos + 1;
  if(next == state->circular_buffer_size)
    next = 0;
  state->pos = next;
  return pushed_out;
}

static inline char get_circular_buffer(const CircularBuffer* const state, const uint32_t pos){
  uint32_t i = state->pos + pos;
  if(i >= state->circular_buffer_size)
    i -= state->circular_buffer_size;
  return state->buf[i];
}

#endif
