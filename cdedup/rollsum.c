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

static void assert(int c, const char* msg){
  if(c == 0){
    printf("ASSERT FAILED: %s\n", msg);
    exit(1);
  }
}

#define RollsumDigest(sum) (((sum)->s2 << 16) | ((sum)->s1 & 0xffff))

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

void push_buffer_rolling(RollingState* const state, const char* const buf, const unsigned len){
  for(unsigned i=0;i<len;i++){
    push_rolling(state, buf[i]);
  }
}

unsigned value_rolling(RollingState* const state) {
  return RollsumDigest(&(state->sum));
}

int main_rollsum() {
  // gcc -g -O2 -Wall -std=c99 rollsum.c circularbuffer.c && time ./a.out
  char* buf = malloc(100000000);
  memset(buf, 'x', 100000000);
  printf("Running\n");
  RollingState* state = create_rolling(1024);
  push_buffer_rolling(state, buf, 100000000);
  destroy_rolling(state);
  free(buf);
  return 0;
};
