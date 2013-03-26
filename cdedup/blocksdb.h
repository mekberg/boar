#ifndef BLOCKSDB_H
#define BLOCKSDB_H

#include "sqlite3.h"

typedef struct _BlockRecord {
  uint8_t  in_use; // Boolean 0 == false
  char     blob[32];
  uint32_t offset; // In blocksize
  char     md5[32];
  char     record_md5[32];
} BlockRecord;


int locate_record(const char* md5);
BlockRecord* get_record(unsigned int pos);

sqlite3* init_blocksdb();

void add_block(sqlite3 *handle, const char* blob, uint32_t offset, const char* md5);

void add_rolling(sqlite3 *handle, uint64_t rolling);
sqlite3_stmt* get_rolling_init(sqlite3 *handle);
int get_rolling_next(sqlite3_stmt* stmt, uint64_t* rolling);
void get_rolling_finish(sqlite3_stmt* stmt);

#endif
