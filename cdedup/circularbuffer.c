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

#include "circularbuffer.h"

#include "stdint.h"
#include "stdlib.h"
#include "stdio.h"
#include "string.h"

static inline void assert(int c, const char* msg){
  if(c == 0){
    printf("ASSERT FAILED: %s\n", msg);
    exit(1);
  }
}

#define SENTINEL (0xDEADBEEF)
#define MAGIC (0xCAFEBABE)

CircularBuffer* create_circular_buffer(const uint32_t window_size){
  CircularBuffer* state = (CircularBuffer*) calloc(1, sizeof(CircularBuffer));
  assert(state != NULL, "CircularBuffer: Failed to allocate memory for state");
  state->magic = MAGIC;
  state->circular_buffer_size = window_size;
  state->buf = calloc(1, window_size);
  assert(state->buf != NULL, "CircularBuffer: Failed to allocate memory for buf");
  state->pos = 0;
  state->length = 0;
  state->sentinel = SENTINEL;

  return state;
}

void destroy_circular_buffer(CircularBuffer* state){
  assert(state != NULL, "CircularBuffer: Tried to destroy null state");
  assert(state->magic == MAGIC, "CircularBuffer: Magic number failed");
  assert(state->sentinel == SENTINEL, "CircularBuffer: Sentinel failed");
  state->magic = 0xFFFFFFFF;
  state->sentinel = 0xFFFFFFFF;
  free(state->buf);
  free(state);
}

void print_circular_buffer(CircularBuffer* state){
  printf("Buffer contents (%u bytes): '", state->length);
  for(uint32_t i=0; i<state->length; i++){
    putchar(get_circular_buffer(state, i));
  }
  printf("'\n");
}


int main_circularbuffer() {
  CircularBuffer* state = create_circular_buffer(3);
  push_circular_buffer(state, 'x');
  push_circular_buffer(state, 'x');
  push_circular_buffer(state, 'x');
  for(int i=0;i<100000000; i++){
    rotate_circular_buffer(state, 'a');
  }
  destroy_circular_buffer(state);
  return 0;
}
