#include "intset.h"

#include "stdlib.h"
#include "stdio.h"
#include "string.h"

static void massert(int condition, const char* message) {
  if(condition == 0){
    printf("Assertion failed: %s\n", message);
    exit(1);
  }
}

IntSet* create_intset(const uint32_t bucket_count) {
  massert(bucket_count > 0, "Bucket count must not be zero");
  IntSet* intset = (IntSet*) calloc(1, sizeof(IntSet));
  intset->bucket_count = bucket_count;
  intset->buckets = (Bucket*) calloc(intset->bucket_count, sizeof(Bucket));
  // intset->filter = bf_create(1); 
  return intset;
}

void add_intset(IntSet* intset, uint32_t int_to_add) {
  Bucket* const bucket = &intset->buckets[int_to_add % intset->bucket_count];
  //bf_set(intset->filter, int_to_add % intset->filter->size, 1);
  if(bucket->slot_count == 0) {
    bucket->slot_count = 1;
    bucket->slots = (uint32_t*) malloc(bucket->slot_count * sizeof(uint32_t));
  } else if(bucket->slot_count == bucket->used_slots){
    // Bucket is full - expand it
    bucket->slot_count *= 2;
    //printf("Expanding bucket %d to size %d\n", int_to_add % intset->bucket_count, bucket->slot_count);
    bucket->slots = (uint32_t*) realloc(bucket->slots, bucket->slot_count * sizeof(uint32_t));
  }
  bucket->slots[bucket->used_slots++] = int_to_add;
}

inline int contains_intset(IntSet* const intset, const uint32_t int_to_find) {
  //if(bf_get(intset->filter, int_to_find % intset->filter->size) == 0){
  //  return 0;
  // }
  Bucket* const bucket = &intset->buckets[int_to_find % intset->bucket_count];
  for(int i=0; i < bucket->used_slots; i++){
    if(bucket->slots[i] == int_to_find){
      return 1;
    }
  }
  return 0;
}

void destroy_intset(IntSet* intset) {
  for(int i=0; i < intset->bucket_count; i++){
    free(intset->buckets[i].slots);
  }
  free(intset->buckets);
  //bf_destroy(intset->filter);
  free(intset);
}


int main_unused() {
  IntSet* const intset = create_intset(10000000);
  massert(intset != NULL, "Couldn't create intset");
  for(int i=0; i<10000000; i++){
    //const int n = rand();
    const int n = 1;
    //if(! contains_intset(intset, n))
    add_intset(intset, n);
    //massert(contains_intset(intset, n), "Value not found after insertion");
  }

  printf("Letar\n");
      
  for(int i=0; i<100000000; i++){
    const int n = rand();
    if(contains_intset(intset, n)){
    }
    //massert(contains_intset(intset, n), "Value not found after insertion");
  }
  destroy_intset(intset);
  return 0;
}
