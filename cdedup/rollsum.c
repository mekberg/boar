#include "rollsum.h"

#include "stdlib.h"
#include "stdio.h"
#include "string.h"
#include "stdint.h"

// Snipped from rsynclib
// (http://stackoverflow.com/questions/6178201/zlib-adler32-rolling-checksum-problem)

void assert(int c, const char* msg){
  if(c == 0){
    printf("ASSERT FAILED: %s\n", msg);
    exit(1);
  }
}

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

#define RollsumDigest64(sum) (						\
			      (((uint64_t)((sum)->s2)) << 32) |		\
			      ((sum)->s1)				\
									)

RollingState* create_rolling(uint32_t window_size){
  RollingState* state = (RollingState*) calloc(1, sizeof(RollingState));
  assert(state != NULL, "create_rolling(): Failed to allocate memory for state");
  state->cb = create_circular_buffer(window_size);
  assert(state->cb != NULL, "create_rolling(): Failed to allocate memory for cb");
  return state;
}

void destroy_rolling(RollingState* state) {
  assert(state != NULL, "destroy_rolling(): Tried to destroy null pointer");
  assert(state->cb != NULL, "destroy_rolling(): State contained null cb");
  destroy_circular_buffer(state->cb);
  free(state);
}

static void massert(int condition, const char* message) {
  if(condition == 0){
    printf("Assertion failed: %s\n", message);
    exit(1);
  }
}

int is_full(RollingState* state) { 
  return is_full_circular_buffer(state->cb);
}

void push_buffer_rolling(RollingState* const state, const char* const buf, const unsigned len){
  for(int i=0;i<len;i++){
    push_rolling(state, buf[i]);
  }
}

void push_rolling(RollingState* const state, const unsigned char c_add) {
  if(!is_full(state)){
    push_circular_buffer(state->cb, c_add);
    RollsumRollin(&state->sum, c_add);
  } else {
    const unsigned char c_remove = rotate_circular_buffer(state->cb, c_add);
    RollsumRotate(&state->sum, c_remove, c_add);
  }
}

unsigned value_rolling(RollingState* const state) {
  return RollsumDigest(&(state->sum));
}

uint64_t value64_rolling(RollingState* const state) {
  return RollsumDigest64(&(state->sum));
}

/*
int main() {
  char* buf = malloc(100000000);
  memset(buf, 'x', 100000000);
  printf("Running\n");
  RollingState* state = create_rolling(1024);
  push_buffer_rolling(state, buf, 100000000);
};
*/
