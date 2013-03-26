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

sqlite3* init_blocksdb(const char* dbfile);

void add_block(sqlite3 *handle, const char* blob, uint32_t offset, const char* md5);

void add_rolling(sqlite3 *handle, uint64_t rolling);
sqlite3_stmt* get_rolling_init(sqlite3 *handle);
int get_rolling_next(sqlite3_stmt* stmt, uint64_t* rolling);
void get_rolling_finish(sqlite3_stmt* stmt);

sqlite3_stmt* get_blocks_init(sqlite3 *handle, char* md5, int limit);
int get_blocks_next(sqlite3_stmt* stmt, char* blob, uint32_t* offset, char* row_md5);
void get_blocks_finish(sqlite3_stmt* stmt);


void begin_blocksdb(sqlite3 *handle);
void commit_blocksdb(sqlite3 *handle);

#endif
