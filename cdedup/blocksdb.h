#ifndef BLOCKSDB_H
#define BLOCKSDB_H

#include "sqlite3.h"

typedef enum BLOCKSDB_RESULT {BLOCKSDB_DONE=1, 
			      BLOCKSDB_ROW, 
			      BLOCKSDB_ERR_CORRUPT, 
			      BLOCKSDB_ERR_OTHER} BLOCKSDB_RESULT;

typedef struct _BlocksDbState {
  uint32_t magic;
  sqlite3* handle;
  sqlite3_stmt* stmt;
  int error_code;
  char error_msg[1024];
} BlocksDbState;

BLOCKSDB_RESULT init_blocksdb(const char* dbfile, BlocksDbState** out_state);

const char* get_error_message(BlocksDbState* dbstate);

BLOCKSDB_RESULT add_block(BlocksDbState* dbstate, const char* blob, uint32_t offset, const char* md5);

void add_rolling(BlocksDbState* dbstate, uint64_t rolling);

BLOCKSDB_RESULT get_rolling_init(BlocksDbState* dbstate);
BLOCKSDB_RESULT get_rolling_next(BlocksDbState* dbstate, uint64_t* rolling);
BLOCKSDB_RESULT get_rolling_finish(BlocksDbState* dbstate);

BLOCKSDB_RESULT get_blocks_init(BlocksDbState* dbstate, char* md5, int limit);
BLOCKSDB_RESULT get_blocks_next(BlocksDbState* dbstate, char* blob, uint32_t* offset, char* row_md5);
BLOCKSDB_RESULT get_blocks_finish(BlocksDbState* dbstate);

int get_modcount(BlocksDbState* dbstate);
void increment_modcount(BlocksDbState* dbstate);

void begin_blocksdb(BlocksDbState* dbstate);
int commit_blocksdb(BlocksDbState* dbstate);

#endif
