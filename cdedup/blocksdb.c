#include "stdlib.h"
#include "stdio.h"
#include "limits.h"
#include "stdint.h"
#include "string.h"

static inline void assert(int c, const char* msg){
  if(c == 0){
    printf("ASSERT FAILED: %s\n", msg);
    exit(1);
  }
}

typedef struct _BlockRecord {
  uint8_t  in_use; // Boolean 0 == false
  char     blob[32];
  uint32_t offset; // In blocksize
  char     md5[32];
  char     record_md5[32];
} BlockRecord;

append_record(FILE* f, BlockRecord* br) {
  fseek(f, 0, SEEK_END);
  fwrite(br, sizeof(BlockRecord), 1, f);
}

load_record(FILE* f, BlockRecord* br) {
  fread(br, sizeof(BlockRecord), 1, f);
}

void populate_file(){
  FILE* f = fopen("/gigant/tmp/blocksdb.mats", "w");
  //BlockRecord* br = calloc(10000000, sizeof(BlockRecord));
  BlockRecord br = {0};
  for(int i=0; i<10000000; i++){
    sprintf(br.md5, "blob%d", i);
    append_record(f, &br);
    //load_record(f, &br[i]);
  }
}

BlockRecord* records;

int locate_record(const char* md5){
  for(int i=0; i<10000000; i++){
    if(strncmp(records[i].md5, md5, 32) == 0){
      return i;
    }
  }
  return -1;
}

int main() {
  FILE* f = fopen("/gigant/tmp/blocksdb.mats", "r");
  records = calloc(10000000, sizeof(BlockRecord));
  for(int i=0; i<10000000; i++){
    load_record(f, &records[i]);
  }
  printf("Position of blob9999999 is %d\n", locate_record("blob9999999"));
}
