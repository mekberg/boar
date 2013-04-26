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
  state->physical_buffer_size = state->circular_buffer_size * 4;
  state->buf = calloc(1, state->physical_buffer_size);
  assert(state->buf != NULL, "CircularBuffer: Failed to allocate memory for buf");
  state->pos = 0;
  // state->next_p = state->buf;
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


static inline void circular_buffer_rebalance(CircularBuffer* state){
  assert(state->magic == MAGIC, "CircularBuffer: Magic failed at rebalance");
  if(state->pos + state->length == state->physical_buffer_size - 1){
    //printf("Rebalancing\n");
    memcpy(state->buf, &state->buf[state->pos], state->length);
    state->pos = 0;
    //state->next_p = state->buf + state->length;
  }
  assert(state->sentinel == SENTINEL, "CircularBuffer: Sentinel failed at rebalance");
}

void inline push_circular_buffer(CircularBuffer* state, const char c) {
  //assert(state->magic == MAGIC, "CircularBuffer: Magic number failed 1");
  //assert(state->sentinel == SENTINEL, "CircularBuffer: Sentinel failed 1");
  circular_buffer_rebalance(state);
  state->buf[state->pos + state->length] = c;
  //printf("Next_p = %u, real_p = %u\n", state->next_p, &state->buf[state->pos + state->length]);
  //*(state->next_p)++ = c;
  if(state->length < state->circular_buffer_size){
    state->length += 1;
  } else {
    state->pos += 1;
  }
  //assert(state->sentinel == SENTINEL, "CircularBuffer: Sentinel failed 2");
}

char get_circular_buffer(CircularBuffer* state, const uint32_t pos){
  assert(pos < state->length, "CircularBuffer: Tried to access position outside window");
  return state->buf[state->pos + pos];
}

char rotate_circular_buffer(CircularBuffer* state, const char c){
  assert(is_full_circular_buffer(state), "CircularBuffer: Tried to rotate a non-full circular buffer");
  const char pushed_out = state->buf[state->pos];
  push_circular_buffer(state, c);
  //printf("Pushed in %c, shifted out %c\n", c, pushed_out);
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


int main_circularbuffer() {
  /*
    Benchmark for 100 MB of data at the time of writing with gcc -O9
    real    0m0.347s
    user    0m0.345s
    sys     0m0.001s

    With gcc -O2
    real    0m0.539s
    user    0m0.535s
    sys     0m0.000s
   */
  CircularBuffer* state = create_circular_buffer(3);
  push_circular_buffer(state, 'x');
  push_circular_buffer(state, 'x');
  push_circular_buffer(state, 'x');
  for(int i=0;i<100000000; i++){
    rotate_circular_buffer(state, 'a');
  }
  destroy_circular_buffer(state);
}

