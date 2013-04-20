#include "intset.h"

#include "stdlib.h"
#include "stdio.h"
#include "time.h"
#include "string.h"
#include "stdint.h"

static void massert(int condition, const char* message) {
  if(condition == 0){
    printf("Assertion failed: %s\n", message);
    exit(1);
  }
}

static int is_power_of_2(const uint32_t n){
  uint32_t c = 1;
  for(unsigned i=0; i<32; i++){
    if(c == n)
      return 1;
    c <<= 1;
  }
  return 0;
}

static void print_stats_intset(IntSet* intset) {
  const int histogram_slot_count = 10;
  uint32_t bucket_size_histogram[histogram_slot_count];
  for(int i=0; i < histogram_slot_count; i++) 
    bucket_size_histogram[i] = 0;
  uint32_t out_of_bounds = 0;
  for(int i=0; i < intset->bucket_count; i++){
    const uint32_t size = intset->buckets[i].used_slots;
    if(size >= histogram_slot_count){
      out_of_bounds += 1;
    } else {
      bucket_size_histogram[size] += 1;
    }
  }
  for(int i=0; i < histogram_slot_count; i++){
    printf("Bucket size %d: %d\n", i, bucket_size_histogram[i]);
  }
  printf("Bucket size >= %d: %d\n", histogram_slot_count, out_of_bounds);
}

#define qmod(a, b) ((a) & ((b)-1))

IntSet* create_intset(const uint32_t bucket_count) {
  massert(bucket_count > 0, "Bucket count must not be zero");
  massert(is_power_of_2(bucket_count), "Bucket count must be a power of 2");
  IntSet* intset = (IntSet*) calloc(1, sizeof(IntSet));
  massert(intset != NULL, "Couldn't allocate intset");
  intset->bucket_count = bucket_count;
  //printf("Allocating %d buckets...\n", intset->bucket_count);
  intset->buckets = (Bucket*) calloc(intset->bucket_count, sizeof(Bucket));
  
  massert(intset->buckets != NULL, "Couldn't allocate buckets for intset");
  return intset;
}

static void grow_intset(IntSet* intset) {
  IntSet* const tmp_intset = create_intset(intset->bucket_count * 2);
  //printf("Growing to size %d\n", tmp_intset->bucket_count);
  for(int bucket_index = 0; bucket_index < intset->bucket_count; bucket_index++){
    Bucket* const bucket = &intset->buckets[qmod(bucket_index, intset->bucket_count)];
    for(int slot_index = 0; slot_index < bucket->used_slots; slot_index++){
      add_intset(tmp_intset, bucket->slots[slot_index]);
    }
  }

  massert(intset->value_count == tmp_intset->value_count, "Grown intset has different number of entries\n");

  for(int i=0; i < intset->bucket_count; i++){
    free(intset->buckets[i].slots);
  }
  free(intset->buckets);

  intset->buckets = tmp_intset->buckets;
  intset->value_count = tmp_intset->value_count;
  intset->bucket_count = tmp_intset->bucket_count;
  free(tmp_intset);
  //printf("Growing complete\n");
}

void add_intset(IntSet* intset, uint64_t int_to_add) {
  Bucket* const bucket = &intset->buckets[qmod(int_to_add, intset->bucket_count)];
  if(bucket->slot_count == 0) {
    bucket->slot_count = 1;
    bucket->slots = (uint64_t*) malloc(bucket->slot_count * sizeof(uint64_t));
    massert(bucket->slots != NULL, "Couldn't allocate slots for bucket");
  } else if(bucket->slot_count == bucket->used_slots){
    // Bucket is full - expand it
    bucket->slot_count *= 2;
    //printf("Expanding bucket %d to size %d\n", int_to_add % intset->bucket_count, bucket->slot_count);
    bucket->slots = (uint64_t*) realloc(bucket->slots, bucket->slot_count * sizeof(uint64_t));
    massert(bucket->slots != NULL, "Couldn't reallocate slots for bucket");
  }
  bucket->slots[bucket->used_slots++] = int_to_add;
  bucket->mask |= int_to_add;
  intset->value_count++;
  if(intset->value_count > intset->bucket_count){
    grow_intset(intset);
  }

}

//static int skipped_searches = 0;

inline int contains_intset(IntSet* const intset, const uint64_t int_to_find) {
  Bucket* const bucket = &intset->buckets[qmod(int_to_find, intset->bucket_count)];
  
  if((bucket->mask & int_to_find) != int_to_find) {
    //skipped_searches++;
    return 0;
  }
  for(unsigned i=0; i < bucket->used_slots; i++){
    if(bucket->slots[i] == int_to_find){
      return 1;
    }
  }
  return 0;
}

void destroy_intset(IntSet* intset) {
  //print_stats_intset(intset);
  for(int i=0; i < intset->bucket_count; i++){
    free(intset->buckets[i].slots);
  }
  free(intset->buckets);
  free(intset);
}

int main_intset() {
  // gcc -g -O2 -Wall -std=c99 intset.c && time ./a.out
  const int size = 8388608;
  IntSet* const intset = create_intset(size*2);
  massert(intset != NULL, "Couldn't create intset");
  
  int* all_values = calloc(size, sizeof(int));    
  for(int i=0; i<size; i++){
    const int n = rand();
    all_values[i] = n;
    add_intset(intset, n);
  }

  int* search_values = calloc(size, sizeof(int));  
  for(int i=0; i<size; i++){
    search_values[i] = rand();
    //search_values[i] = i;
  }

  for(int i=0; i<size; i++){
    // Make sure all inserted values are actually there
    massert(contains_intset(intset, all_values[i]), "An inserted value is missing");
  }  

  printf("Searching\n");
  const clock_t t0 = clock();
  int found = 0;
  int queries = 0;
  for(int n=0; n<10; n++) {
    for(int i=0; i < size; i++){
      queries += 1;
      if(contains_intset(intset, search_values[i])){
	found += 1;
      }
    }
  }
  const clock_t t1 = clock();
  const clock_t ms = (t1 - t0) / (CLOCKS_PER_SEC/1000);
  printf("RAND_MAX=%d\n", RAND_MAX);
  printf("Found %d hits of %d queries in %ld ms (%d entries)\n", found, queries, ms, intset->value_count);
  const int mb_per_second = queries / ms / 1024;
  //printf("Mask caused %d linear searches to be skipped\n", skipped_searches);
  printf("Search speed %d Mb/s\n", mb_per_second);
  destroy_intset(intset);
  free(search_values);
  return 0;
}
