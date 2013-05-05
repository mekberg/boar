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

#include "rollsum.h"

#include "stdlib.h"
#include "stdio.h"
#include "string.h"
#include "stdint.h"

// Snipped from rsynclib
// (http://stackoverflow.com/questions/6178201/zlib-adler32-rolling-checksum-problem)

static void assert(int c, const char* msg){
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
  for(unsigned i=0;i<len;i++){
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


int main_rollsum() {
  // gcc -g -O2 -Wall -std=c99 rollsum.c circularbuffer.c && time ./a.out
  /* Benchmark results at the time of writing for 100 MB
     real    0m1.134s
     user    0m1.098s
     sys     0m0.035s
  */
  char* buf = malloc(100000000);
  memset(buf, 'x', 100000000);
  printf("Running\n");
  RollingState* state = create_rolling(1024);
  push_buffer_rolling(state, buf, 100000000);
  destroy_rolling(state);
  free(buf);
};

