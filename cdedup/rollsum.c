#include "rollsum.h"

#include "stdlib.h"
#include "stdio.h"
#include "string.h"

// Snipped from rsynclib
// (http://stackoverflow.com/questions/6178201/zlib-adler32-rolling-checksum-problem)

#define ROLLSUM_CHAR_OFFSET 31


#define RollsumInit(sum) { \
  (sum)->count=(sum)->s1=(sum)->s2=0; \
  }

#define RollsumRotate(sum,out,in) { \
  (sum)->s1 += (unsigned char)(in) - (unsigned char)(out); \
  (sum)->s2 += (sum)->s1 - (sum)->count*((unsigned char)(out)+ROLLSUM_CHAR_OFFSET); \
  }

#define RollsumRollin(sum,c) { \
  (sum)->s1 += ((unsigned char)(c)+ROLLSUM_CHAR_OFFSET); \
  (sum)->s2 += (sum)->s1; \
  (sum)->count++; \
  }

#define RollsumRollout(sum,c) { \
  (sum)->s1 -= ((unsigned char)(c)+ROLLSUM_CHAR_OFFSET); \
  (sum)->s2 -= (sum)->count*((unsigned char)(c)+ROLLSUM_CHAR_OFFSET); \
  (sum)->count--; \
  }

#define RollsumDigest(sum) (((sum)->s2 << 16) | ((sum)->s1 & 0xffff))

RollingState* create_rolling(int window_size){
  RollingState* state = (RollingState*) calloc(1, sizeof(RollingState));
  state->cbuf = calloc(1, window_size + 1);
  state->size = window_size+1;
  return state;
}

void destroy_rolling(RollingState* state) {
  free(state->cbuf);
  free(state);
}

static void massert(int condition, const char* message) {
  if(condition == 0){
    printf("Assertion failed: %s\n", message);
    exit(1);
  }
}

int is_full(RollingState* state) { 
  return (state->pe + 1) % state->size == state->ps;
}

int is_empty(RollingState* state) { 
  return state->pe == state->ps;
}

static void push_char(RollingState* state, unsigned char c_push){
  massert(! is_full(state), "push_char(): Circular buffer is full");
  state->cbuf[state->pe] = c_push;
  state->pe = (state->pe + 1) % state->size;
}

static unsigned char shift_char(RollingState* state){
  massert(! is_empty(state), "shift_char(): Circular buffer is empty");
  unsigned char c = state->cbuf[state->ps];
  state->ps = (state->ps + 1) % state->size;
  return c;
}

static void copy_rolling_buffer(RollingState* state, char* target_buffer, int target_buffer_size){
  int p = state->ps;
  massert(target_buffer_size >= state->size, "copy_rolling_buffer(): too small output buffer");
  memset(target_buffer, 0, target_buffer_size);
  while(p != state->pe){
    *target_buffer++ = state->cbuf[p];
    p = (p + 1) % state->size;
  }
}

void push_rolling(RollingState* const state, const unsigned char c_add) {
  if(!is_full(state)){
    RollsumRollin(&state->sum, c_add);
  } else {
    const unsigned char c_remove = shift_char(state);
    RollsumRotate(&state->sum, c_remove, c_add);
  }
  push_char(state, c_add);
}

unsigned value_rolling(RollingState* const state) {
  return RollsumDigest(&(state->sum));
}

static void print_rolling(RollingState* const state){
  unsigned digest = RollsumDigest(&(state->sum));
  char buf[state->size+1];
  memset(buf, 0, sizeof(buf));
  copy_rolling_buffer(state, buf, sizeof(buf));
  printf("ps=%d pe=%d buffer='%s' digest=%u\n", state->ps, state->pe, buf, digest);
}

