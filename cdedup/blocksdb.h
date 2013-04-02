#ifndef BLOCKSDB_H
#define BLOCKSDB_H

#include "sqlite3.h"

enum BLOCKSDB_RESULT {BLOCKSDB_OK=1, BLOCKSDB_ERR_CORRUPT, BLOCKSDB_ERR_OTHER};

typedef struct _BlocksDbState {
  uint32_t magic;
  sqlite3* handle;
  sqlite3_stmt* stmt;
  int error_code;
  char error_msg[1024];
} BlocksDbState;

BlocksDbState* init_blocksdb(const char* dbfile);

void add_block(BlocksDbState* dbstate, const char* blob, uint32_t offset, const char* md5);

void add_rolling(BlocksDbState* dbstate, uint64_t rolling);
int get_rolling_init(BlocksDbState* dbstate);
int get_rolling_next(BlocksDbState* dbstate, uint64_t* rolling);
int get_rolling_finish(BlocksDbState* dbstate);

sqlite3_stmt* get_blocks_init(BlocksDbState* dbstate, char* md5, int limit);
int get_blocks_next(sqlite3_stmt* stmt, char* blob, uint32_t* offset, char* row_md5);
void get_blocks_finish(sqlite3_stmt* stmt);

int get_modcount(BlocksDbState* dbstate);
void increment_modcount(BlocksDbState* dbstate);

void begin_blocksdb(BlocksDbState* dbstate);
int commit_blocksdb(BlocksDbState* dbstate);

#endif
