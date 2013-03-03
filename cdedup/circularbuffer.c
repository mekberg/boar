#include "circularbuffer.h"

#include "stdint.h"
#include "stdlib.h"
#include "stdio.h"
#include "string.h"

static void assert(int c, const char* msg){
  if(c == 0){
    printf("ASSERT FAILED: %s\n", msg);
    exit(1);
  }
}

CircularBuffer* create_circular_buffer(const uint32_t window_size){
  CircularBuffer* state = (CircularBuffer*) calloc(1, sizeof(CircularBuffer));
  assert(state != NULL, "CircularBuffer: Failed to allocate memory for state");
  state->circular_buffer_size = window_size;
  state->physical_buffer_size = state->circular_buffer_size * 4;
  state->buf = calloc(1, state->physical_buffer_size);
  assert(state->buf != NULL, "CircularBuffer: Failed to allocate memory for buf");
  state->pos = 0;
  state->length = 0;
  state->sentinel = 0xDEADBEEF;
  return state;
}

void destroy_circular_buffer(CircularBuffer* state){
  assert(state != NULL, "CircularBuffer: Tried to destroy null state");
  free(state->buf);
  assert(state->sentinel == 0xDEADBEED, "CircularBuffer: Sentinel failed");
  free(state);
}


static void circular_buffer_rebalance(CircularBuffer* state){
  if(state->pos + state->length == state->physical_buffer_size - 1){
    //printf("Rebalancing\n");
    memcpy(state->buf, &state->buf[state->pos], state->length);
    state->pos = 0;
  }
}

void push_circular_buffer(CircularBuffer* state, const char c) {
  circular_buffer_rebalance(state);
  state->buf[state->pos + state->length] = c;
  if(state->length < state->circular_buffer_size){
    state->length += 1;
  } else {
    state->pos += 1;
  }
}

char get_circular_buffer(CircularBuffer* state, const uint32_t pos){
  assert(pos < state->length, "CircularBuffer: Tried to access position outside window");
  return state->buf[state->pos + pos];
}

char rotate_circular_buffer(CircularBuffer* state, const char c){
  assert(is_full_circular_buffer(state), "CircularBuffer: Tried to rotate a non-full circular buffer");
  char pushed_out = state->buf[state->pos];
  push_circular_buffer(state, c);
  return pushed_out;
}

int is_full_circular_buffer(CircularBuffer* state){
  return state->length == state->circular_buffer_size;
}

void print_circular_buffer(CircularBuffer* state){
  printf("Buffer contents (%u bytes): '", state->length);
  for(int i=0; i<state->length; i++){
    putchar(get_circular_buffer(state, i));
  }
  printf("'\n");
}

/*

int main() {
  CircularBuffer* state = create_circular_buffer(3);
  push_circular_buffer(state, 'a');
  push_circular_buffer(state, 'b');
  push_circular_buffer(state, 'c');
  for(int i=0;i<100000000; i++){
    rotate_circular_buffer(state, 'j');
  }
  push_circular_buffer(state, 'd');
  push_circular_buffer(state, 'e');
  push_circular_buffer(state, 'f');
  push_circular_buffer(state, 'g');
  push_circular_buffer(state, 'h');
  push_circular_buffer(state, 'i');
  push_circular_buffer(state, 'j');
}

*/
