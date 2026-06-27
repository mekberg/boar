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
void destroy_rolling(RollingState* state);
void push_buffer_rolling(RollingState* state, const char* buf, unsigned len);
unsigned value_rolling(RollingState* state);

// Snipped from rsynclib
// (http://stackoverflow.com/questions/6178201/zlib-adler32-rolling-checksum-problem)

#define ROLLSUM_CHAR_OFFSET 31

#define RollsumRotate(sum,out,in) { \
  (sum)->s1 += (unsigned char)(in) - (unsigned char)(out); \
  (sum)->s2 += (sum)->s1 - (sum)->count*((unsigned char)(out)+ROLLSUM_CHAR_OFFSET); \
  }

#define RollsumRollin(sum,c) { \
  (sum)->s1 += ((unsigned char)(c)+ROLLSUM_CHAR_OFFSET); \
  (sum)->s2 += (sum)->s1; \
  (sum)->count++; \
  }

#define RollsumDigest64(sum) (						\
			      (((uint64_t)((sum)->s2)) << 32) |		\
			      ((sum)->s1)				\
								)

// The per-byte hot path. Kept "static inline" in the header so it
// folds directly into the scanning loop in the Cython-generated code
// (which #includes this header), eliminating one cross-module call
// per input byte.
static inline int is_full(const RollingState* const state) {
  return is_full_circular_buffer(state->cb);
}

static inline void push_rolling(RollingState* const state, const unsigned char c_add) {
  if(!is_full_circular_buffer(state->cb)){
    push_circular_buffer(state->cb, c_add);
    RollsumRollin(&state->sum, c_add);
  } else {
    const unsigned char c_remove = rotate_circular_buffer(state->cb, c_add);
    RollsumRotate(&state->sum, c_remove, c_add);
  }
}

static inline uint64_t value64_rolling(const RollingState* const state) {
  return RollsumDigest64(&(state->sum));
}

#endif
