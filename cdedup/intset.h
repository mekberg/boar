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
int contains_intset(IntSet* intset, uint64_t int_to_find);
void destroy_intset(IntSet* intset);

#endif
