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

BLOCKSDB_RESULT init_blocksdb(const char* dbfile, int block_size, BlocksDbState** out_state);
BLOCKSDB_RESULT close_blocksdb(BlocksDbState* dbstate);

const char* get_error_message(BlocksDbState* dbstate);

BLOCKSDB_RESULT add_block(BlocksDbState* dbstate, const char* blob, uint64_t offset, const char* md5);

BLOCKSDB_RESULT add_rolling(BlocksDbState* dbstate, uint64_t rolling);

BLOCKSDB_RESULT get_rolling_init(BlocksDbState* dbstate);
BLOCKSDB_RESULT get_rolling_next(BlocksDbState* dbstate, uint64_t* rolling);
BLOCKSDB_RESULT get_rolling_finish(BlocksDbState* dbstate);

BLOCKSDB_RESULT get_blocks_init(BlocksDbState* dbstate, char* md5, int limit);

/** Get the next row of the result. The blob name will be written to
 *  the position pointed to by the 'blob' parameter. The blob name is
 *  33 bytes long, including a terminating null char. 
 */
BLOCKSDB_RESULT get_blocks_next(BlocksDbState* dbstate, char* out_blob, uint64_t* out_offset);
BLOCKSDB_RESULT get_blocks_finish(BlocksDbState* dbstate);

BLOCKSDB_RESULT delete_blocks_init(BlocksDbState* dbstate);
BLOCKSDB_RESULT delete_blocks_add(BlocksDbState* dbstate, char* blob);
BLOCKSDB_RESULT delete_blocks_finish(BlocksDbState* dbstate);

BLOCKSDB_RESULT get_modcount(BlocksDbState* dbstate, int* out_modcount);
BLOCKSDB_RESULT increment_modcount(BlocksDbState* dbstate);

BLOCKSDB_RESULT get_block_size(BlocksDbState* dbstate, int* out_block_size);

BLOCKSDB_RESULT begin_blocksdb(BlocksDbState* dbstate);
BLOCKSDB_RESULT commit_blocksdb(BlocksDbState* dbstate);

#endif
