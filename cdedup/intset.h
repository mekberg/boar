#ifndef INTSET_H
#define INTSET_H

#include <stdint.h>

typedef struct _Bucket {
  uint32_t slot_count;
  uint32_t used_slots;
  uint32_t* slots; // An array of size "slot_count" where the first "used_slots" contains valid data.
} Bucket;

typedef struct _IntSet {
  uint32_t bucket_count; // Must be a power of 2
  Bucket* buckets; // An array of bucket_count buckets
} IntSet;

IntSet* create_intset(uint32_t bucket_count);
void add_intset(IntSet* intset, uint32_t int_to_add);
int contains_intset(IntSet* intset, uint32_t int_to_find);
void destroy_intset(IntSet* intset);

#endif
