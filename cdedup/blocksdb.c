#include "stdlib.h"
#include "stdio.h"
#include "limits.h"
#include "stdint.h"
#include "string.h"
#include "md5.h"
#include "time.h"

#include "blocksdb.h"

static inline void assert(int c, const char* msg){
  if(c == 0){
    printf("ASSERT FAILED: %s\n", msg);
    exit(1);
  }
}

void append_record(FILE* f, BlockRecord* br) {
  fseek(f, 0, SEEK_END);
  size_t result = fwrite(br, sizeof(BlockRecord), 1, f);
  assert(result == 1, "fwrite failed");
}

void load_record(FILE* f, BlockRecord* br) {
  size_t result = fread(br, sizeof(BlockRecord), 1, f);
  assert(result == 1, "fread failed");
}

void populate_file(){
  FILE* f = fopen("/gigant/tmp/blocksdb.mats", "w");
  BlockRecord br = {0};
  char tmp[100];
  for(int i=0; i<10000000; i++){
    sprintf(tmp, "block%d", i);
    sprintf(br.blob, "blob%d", i/100);    
    md5_buf(tmp, strlen(tmp), br.md5);
    append_record(f, &br);
  }
}

BlockRecord* records;
#define NO_OF_RECORDS 10000000

int locate_record_linear(const char* md5){
  for(int i=0; i<NO_OF_RECORDS; i++){
    if(strncmp(records[i].md5, md5, 32) == 0){
      return i;
    }
  }
  return -1;
}

BlockRecord* get_record(unsigned int pos){
  assert(pos < NO_OF_RECORDS, "Tried to access position outside of db");
  return &records[pos];
}

int locate_record(const char* md5){
  int low = 0;
  int high = NO_OF_RECORDS - 1;  
  int found = -1;
  while(1){
    //printf("low=%d, high=%d\n", low, high);
    int mid = low + (high-low)/2;
    int cmp = strncmp(records[mid].md5, md5, 32);
    if(cmp < 0) {
      high = mid;
    } else if(cmp > 0){
      low = mid;
    } else {
      found = mid;
      break;
    }
    if (low == high) {
      if(strncmp(records[low].md5, md5, 32) == 0) {
	found = low;
	break;
      }
      return -1;
    }
  }
  /* We have found a hit. Now let's make sure it is the lowest
     existing hit.*/
  assert(found >= 0, "locate_record() error");
  while(found != 0){
    if(strcmp(records[found-1].md5, md5) == 0) {
      found -= 1;
    } else {
      break;
    }
  }
  return found;
}

int block_comparer(const void* a, const void* b) {
  BlockRecord* br1 = (BlockRecord*) a;
  BlockRecord* br2 = (BlockRecord*) b;
  return strcmp(br2->md5, br1->md5);
}

void sort_records(){
  qsort(records, NO_OF_RECORDS, sizeof(BlockRecord), block_comparer);
}

int main_md5(){
  char md5[33];
  md5[32] = '\0';
  const char* buf = "";
  md5_buf(buf, strlen(buf), md5);
  printf("Md5 is %s\n", md5);
  return 0;
}

int main() {
  FILE* f = fopen("/gigant/tmp/blocksdb.mats", "r");
  records = calloc(NO_OF_RECORDS, sizeof(BlockRecord));
  for(int i=0; i<NO_OF_RECORDS; i++){
    load_record(f, &records[i]);
  }
  printf("Sorting...\n");
  sort_records();
  printf("Sorting done\n");
  clock_t t0 = clock();
  int pos;
  for(int i=0; i<1000000; i++){
    pos = locate_record("5977135243874914d8da8abd87bebec6");
  }
  printf("Position of blob is %d\n", pos);
  clock_t dt = clock() - t0;
  printf ("It took %d clicks (%f seconds).\n", (int)dt,((float)dt)/CLOCKS_PER_SEC);
  return 0;
}
