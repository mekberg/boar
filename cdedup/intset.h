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

#ifndef INTSET_H
#define INTSET_H

#include <stdint.h>

typedef struct _Bucket {
  uint64_t mask; // The OR of all values in this bucket
  uint32_t used_slots;
  uint32_t slot_count;
  uint64_t* slots; // An array of size "slot_count" where the first "used_slots" contains valid data.
} Bucket;

typedef struct _IntSet {
  uint32_t value_count;
  uint32_t bucket_count; // Must be a power of 2
  Bucket* buckets; // An array of bucket_count buckets
  uint32_t magic;
} IntSet;

IntSet* create_intset(uint32_t bucket_count);
void add_intset(IntSet* intset, uint64_t int_to_add);
void destroy_intset(IntSet* intset);

// This function is a hot spot - it is called once per input byte from
// the scanning loop. It is kept "static inline" in the header so it
// folds directly into the Cython-generated caller. The per-bucket
// "mask" (the OR of every value in the bucket) lets us reject the
// common miss case with a single load and compare, before touching
// the slot array at all.
static inline int contains_intset(const IntSet* const intset, const uint64_t int_to_find) {
  const Bucket* const bucket = &intset->buckets[int_to_find & (intset->bucket_count - 1)];

  if((bucket->mask & int_to_find) != int_to_find) {
    return 0;
  }
  for(uint32_t i=0; i < bucket->used_slots; i++){
    if(bucket->slots[i] == int_to_find){
      return 1;
    }
  }
  return 0;
}

#endif
