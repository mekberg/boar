// Copyright 2013 Mats Ekberg
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include "stdlib.h"
#include "stdio.h"
#include "stdint.h"
#include "string.h"
#include "time.h"

#include "sqlite3.h"
#include "blocksdb.h"

#include "crc16.h"

#define false 0
#define max_log_entry_size 1024

#ifdef ENABLE_BLOCKSDB_LOGGING
#define LOG_ENTER() {							\
    char msg[max_log_entry_size];					\
    const int n = snprintf(msg, max_log_entry_size, "entering %s:%u",	\
			   __func__, __LINE__);				\
    if(n < max_log_entry_size) {					\
      blocksdb_log(msg);						\
    }									\
  }

#define LOG_EXIT() {							\
    char msg[max_log_entry_size];					\
    snprintf(msg, max_log_entry_size, "exiting %s:%u",			\
	     __func__, __LINE__);					\
    if(n < max_log_entry_size) {					\
      blocksdb_log(msg);						\
    }									\
  }
#else

#define LOG_ENTER()
#define LOG_EXIT()

#endif

/* This macro returns the given error string, joined with the current
 * sqlite error state information.
 */
#define RET_SQLITE_ERROR(msg) {						\
    sprintf(dbstate->error_msg, msg "(%s:%u: error %d:%s)",		\
	    __FILE__, __LINE__, sqlite3_errcode(dbstate->handle),	\
	    sqlite3_errmsg(dbstate->handle));				\
    LOG_EXIT();								\
    return BLOCKSDB_ERR_OTHER;						\
  }

#define RET_ERROR_CORRUPT(msg) {					\
    sprintf(dbstate->error_msg, msg "(%s:%u: %s)",			\
	    __FILE__, __LINE__, "blocks database is corrupt");		\
    LOG_EXIT();								\
    return BLOCKSDB_ERR_CORRUPT;					\
  }

#define RET_ERROR_OTHER(msg)  {						\
    sprintf(dbstate->error_msg, msg "(%s:%u)",				\
	    __FILE__, __LINE__);					\
    LOG_EXIT();								\
    return BLOCKSDB_ERR_OTHER;						\
  }

#define ASSERT_VALID_STATE(dbstate) 					\
  if(dbstate->magic != 0xabcd1234) {					\
    printf("Invalid blocksdb magic number at %s:%u",			\
	   __FILE__, __LINE__);						\
    assert(false, "invalid magic number");				\
  }


static inline void assert(int c, const char* msg){
  if(c == 0){
    printf("ASSERT FAILED: %s\n", msg);
    exit(1);
  }
}

#include "unistd.h"
#include "sys/time.h"

static void blocksdb_log(const char* msg ) { 
  static FILE* log = NULL;
  char logfile[] = "/tmp/boar-blocksdb-log.txt";
  if(log == NULL)
    log = fopen(logfile, "a");
  assert(log, "Couldn't open log file");
  struct timeval tv;
  gettimeofday(&tv, NULL);
  const long long time_in_mill = 
    (tv.tv_sec) * 1000000 + (tv.tv_usec)  - 1366644831735000ll;  
  fprintf(log, "%lld {PID %d} %s\n", time_in_mill, getpid(), msg); 
}

#ifdef ENABLE_BLOCKSDB_LOGGING
static void trace_callback( void* udp, const char* sql ) { 
  char logmsg[1024];
  snprintf(logmsg, 1024, "[%s]", sql);
  blocksdb_log(logmsg);
} 
#endif

static int hexchar2bin(const char c) {
  switch(c) {
  case '0': return 0;
  case '1': return 1;
  case '2': return 2;
  case '3': return 3;
  case '4': return 4;
  case '5': return 5;
  case '6': return 6;
  case '7': return 7;
  case '8': return 8;
  case '9': return 9;
  case 'a':
  case 'A': return 10;
  case 'b': 
  case 'B': return 11;
  case 'c': 
  case 'C': return 12;
  case 'd': 
  case 'D': return 13;
  case 'e': 
  case 'E': return 14;
  case 'f': 
  case 'F': return 15;
  default:
    return -1;
  }
}

static int is_md5sum(const char* buf){
  for(int i = 0; i < 32; i++) {
    if(hexchar2bin(buf[i]) == -1){
      return 0;
    }
  }
  return 1;
}

static int hex2bin(const char* hex_buf, int hex_buf_length, char* bin_buf){
  for(int i = 0; i < hex_buf_length/2; i++) {
    bin_buf[i] = hexchar2bin(hex_buf[i*2]) << 4;
    bin_buf[i] |= hexchar2bin(hex_buf[i*2 + 1]);
  }
  return 1;
}

static int bin2hex(const char* bin_buf, int bin_buf_length, char* hex_buf) {
  char byte_hex[3]; 
  for(int i = 0; i < bin_buf_length; i++) {
    assert(snprintf(byte_hex, 3, "%02x", (unsigned char) bin_buf[i]) == 2, "Unexpected bin2hex snprintf result");
    *hex_buf++ = byte_hex[0];
    *hex_buf++ = byte_hex[1];
  }
  return 1;
}

static void pack_md5(const char* md5_hex, char* md5_bin) {
  assert(is_md5sum(md5_hex), "Argument to pack_md5() was not a legal md5 checksum");
  hex2bin(md5_hex, 32, md5_bin);
}

static void unpack_md5(const char* md5_bin, char* md5_hex) {
  bin2hex(md5_bin, 16, md5_hex);
  assert(is_md5sum(md5_hex), "Result of unpack_md5() was not a legal md5 checksum");
}

static uint16_t crc16_row(const char* const blob, const uint64_t offset, const char* const md5) {
  const int max_size = 200;
  char crc_data[max_size];
  const int crc_data_len = snprintf(crc_data, max_size, "%s!%llu!%s!", blob, (long long unsigned) offset, md5);
  assert(crc_data_len > 0 && crc_data_len < max_size, "crc snprintf() failed");
  return crc16(crc_data, (unsigned short) crc_data_len);
}

static BLOCKSDB_RESULT execute_simple(BlocksDbState* dbstate, char* sql) {
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  int retval =  sqlite3_exec(dbstate->handle, sql, NULL, NULL, NULL);
  if(retval != SQLITE_OK){
    strcpy(dbstate->error_msg, sqlite3_errmsg(dbstate->handle));
    return BLOCKSDB_ERR_OTHER;
  }
  LOG_EXIT();
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT get_rolling_init(BlocksDbState* dbstate){
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  // TODO: error if a stmt is already active
  assert(dbstate->stmt == NULL, "get_rolling_init(): Tried to create a second cursor");
  const int s = sqlite3_prepare_v2(dbstate->handle, "SELECT value FROM rolling", -1, &dbstate->stmt, NULL);
  if (s == SQLITE_OK) {
    LOG_EXIT();
    return BLOCKSDB_DONE;
  }
  sprintf(dbstate->error_msg, 
	  "Error while initializing fetching rolling checksums: %s", 
	  sqlite3_errmsg(dbstate->handle));
  return BLOCKSDB_ERR_OTHER; // Should never get here
}

BLOCKSDB_RESULT get_rolling_next(BlocksDbState* dbstate, uint64_t *rolling) {
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  int s = sqlite3_step (dbstate->stmt);
  if (s == SQLITE_ROW) {    
    *rolling = (uint64_t) sqlite3_column_int64(dbstate->stmt, 0); 
    LOG_EXIT();
    return BLOCKSDB_ROW;
  }
  else if (s == SQLITE_DONE) { 
    LOG_EXIT();
    return BLOCKSDB_DONE;
  }
  sprintf(dbstate->error_msg, 
	  "Error while fetching rolling checksums (sqlite error %d): %s", 
	  s, sqlite3_errmsg(dbstate->handle));
  return BLOCKSDB_ERR_OTHER; // Should never get here
}

BLOCKSDB_RESULT get_rolling_finish(BlocksDbState* dbstate) {
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  sqlite3_finalize(dbstate->stmt);
  dbstate->stmt = NULL;
  LOG_EXIT();
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT add_rolling(BlocksDbState* dbstate, uint64_t rolling){
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  sqlite3_stmt* stmt;
  if(SQLITE_OK != sqlite3_prepare_v2(dbstate->handle, "INSERT INTO rolling (value) VALUES (?)",
				     -1, &stmt, NULL))
    RET_SQLITE_ERROR("Couldn't prepare statement in add_rolling()");
  if(SQLITE_OK != sqlite3_bind_int64(stmt, 1, (sqlite3_int64) rolling))
    RET_SQLITE_ERROR();
  if(SQLITE_DONE != sqlite3_step(stmt)) {
    RET_SQLITE_ERROR("Unexpected step result in add_rolling()");
  }
  if(SQLITE_OK != sqlite3_finalize(stmt))
    RET_SQLITE_ERROR();  
  LOG_EXIT();
  return BLOCKSDB_DONE;
}


BLOCKSDB_RESULT add_block(BlocksDbState* dbstate, const char* blob, uint64_t offset, const char* md5){
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  //const char* md5_row = block_row_checksum(blob, offset, md5);
  if(! is_md5sum(blob)) {
    sprintf(dbstate->error_msg, "add_block(): Not a valid blob name: %s", blob);    
    LOG_EXIT();
    return BLOCKSDB_ERR_OTHER;
  }
  if(! is_md5sum(md5)) {
    sprintf(dbstate->error_msg, "add_block(): Not a valid md5 sum: %s", md5);    
    LOG_EXIT();
    return BLOCKSDB_ERR_OTHER;
  }

  const uint16_t row_crc = crc16_row(blob, offset, md5);

  char packed_md5[16];
  pack_md5(md5, packed_md5);
  char packed_blob[16];
  pack_md5(blob, packed_blob);
  sqlite3_stmt* stmt;

  if(SQLITE_OK != sqlite3_prepare_v2(dbstate->handle, "INSERT OR IGNORE INTO blocks (blob, offset, md5_short, md5, row_crc) VALUES (?, ?, ?, ?, ?)",
				     -1, &stmt, NULL)) {
    RET_SQLITE_ERROR("Error while preparing add_block()");
  }
  
  if(SQLITE_OK != sqlite3_bind_blob(stmt, 1, packed_blob, 16, SQLITE_STATIC)) 
    RET_SQLITE_ERROR();
  if(SQLITE_OK != sqlite3_bind_int64(stmt, 2, (int64_t) offset))
    RET_SQLITE_ERROR();
  if(SQLITE_OK != sqlite3_bind_blob(stmt, 3, packed_md5, 4, SQLITE_STATIC))
    RET_SQLITE_ERROR();
  if(SQLITE_OK != sqlite3_bind_blob(stmt, 4, packed_md5, 16, SQLITE_STATIC))
    RET_SQLITE_ERROR();
  if(SQLITE_OK != sqlite3_bind_int(stmt, 5, row_crc))
    RET_SQLITE_ERROR();

  if(SQLITE_DONE != sqlite3_step(stmt))
    RET_SQLITE_ERROR("Error while inserting new block");

  if(SQLITE_OK != sqlite3_finalize(stmt))
    RET_SQLITE_ERROR();
  LOG_EXIT();
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT get_blocks_init(BlocksDbState* dbstate, char* md5, int limit){
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  if(! is_md5sum(md5)) {
    sprintf(dbstate->error_msg, "get_blocks_init(): Not a valid md5 sum: %s", md5);    
    LOG_EXIT();
    return BLOCKSDB_ERR_OTHER;
  }
  int retval;
  retval = sqlite3_prepare_v2(dbstate->handle, "SELECT blocks.blob, blocks.offset, blocks.row_crc, blocks.md5 FROM blocks WHERE md5_short = ? AND md5 = ? LIMIT ?",
                              -1, &dbstate->stmt, NULL);
  if(retval != SQLITE_OK){
    RET_SQLITE_ERROR("get_blocks_init() prepare failed");
  }

  char packed_md5[16];
  pack_md5(md5, packed_md5);

  if(SQLITE_OK != sqlite3_bind_blob(dbstate->stmt, 1, packed_md5, 4, SQLITE_TRANSIENT))
    RET_SQLITE_ERROR();
  if(SQLITE_OK != sqlite3_bind_blob(dbstate->stmt, 2, packed_md5, 16, SQLITE_TRANSIENT))
    RET_SQLITE_ERROR();
  if(SQLITE_OK != sqlite3_bind_int(dbstate->stmt, 3, limit))
    RET_SQLITE_ERROR();
  LOG_EXIT();
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT get_blocks_next(BlocksDbState* dbstate, char* blob, uint64_t* offset) {
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  int s = sqlite3_step (dbstate->stmt);
  if (s == SQLITE_ROW) {
    // TODO: verify integrity
    const char* blob_col = (const char*) sqlite3_column_text(dbstate->stmt, 0);
    const int blob_col_length = sqlite3_column_bytes(dbstate->stmt, 0);
    if(blob_col_length != 16)
      RET_ERROR_CORRUPT("Unexpected blob column length in get_blocks_next()");
    unpack_md5(blob_col, blob);
    blob[32] = '\0';

    *offset = (uint64_t) sqlite3_column_int64(dbstate->stmt, 1);
    
    const int row_crc = sqlite3_column_int(dbstate->stmt, 2);

    const char* md5_col = (const char*) sqlite3_column_text(dbstate->stmt, 3);
    const int md5_col_length = sqlite3_column_bytes(dbstate->stmt, 3);
    if(md5_col_length != 16)
      RET_ERROR_CORRUPT("Unexpected md5 column length in get_blocks_next()");
    char md5[33];
    unpack_md5(md5_col, md5);
    md5[32] = '\0';

    const unsigned short expected_row_crc = crc16_row(blob, *offset, md5);

    if(row_crc != expected_row_crc){
      sprintf(dbstate->error_msg, "An entry in the blocks database is corrupt (block id %s)", md5);
      LOG_EXIT();
      return BLOCKSDB_ERR_CORRUPT;
    }
    LOG_EXIT();
    return BLOCKSDB_ROW;
  }
  else if (s == SQLITE_DONE) {
    LOG_EXIT();
    return BLOCKSDB_DONE;
  }
  assert(false, "Unexpected result in get_all_rolling_next");
  return BLOCKSDB_ERR_OTHER; // should never get here
}

BLOCKSDB_RESULT get_blocks_finish(BlocksDbState* dbstate) {
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  assert(dbstate->stmt != NULL, "Tried to call get_blocks_finish() with no active cursor");
  if(SQLITE_OK != sqlite3_finalize(dbstate->stmt))
    RET_SQLITE_ERROR();
  dbstate->stmt = NULL;
  LOG_EXIT();
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT delete_blocks_init(BlocksDbState* dbstate){
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  BLOCKSDB_RESULT result = execute_simple(dbstate, "CREATE TEMPORARY TABLE blocks_to_delete (blob CHAR(16) PRIMARY KEY)");
  LOG_EXIT();
  return result;
}

BLOCKSDB_RESULT delete_blocks_add(BlocksDbState* dbstate, char* blob){
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  if(! is_md5sum(blob)) {
    sprintf(dbstate->error_msg, "delete_blocks_add(): Not a valid blob name: %s", blob);
    LOG_EXIT();
    return BLOCKSDB_ERR_OTHER;
  }
  char packed_blob[16];
  pack_md5(blob, packed_blob);
  sqlite3_stmt* stmt;

  if(SQLITE_OK != sqlite3_prepare_v2(dbstate->handle, "INSERT OR IGNORE INTO blocks_to_delete (blob) VALUES (?)",
				     -1, &stmt, NULL)) {
    RET_SQLITE_ERROR("Error while preparing delete_blocks_add()");
  }
  if(SQLITE_OK != sqlite3_bind_blob(stmt, 1, packed_blob, 16, SQLITE_STATIC))
    RET_SQLITE_ERROR();

  if(SQLITE_DONE != sqlite3_step(stmt))
    RET_SQLITE_ERROR("Error while adding blob to list of blocks to delete");

  if(SQLITE_OK != sqlite3_finalize(stmt))
    RET_SQLITE_ERROR();
  
  LOG_EXIT();
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT delete_blocks_finish(BlocksDbState* dbstate){
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  BLOCKSDB_RESULT result = execute_simple(dbstate, "DELETE FROM blocks WHERE blocks.blob IN blocks_to_delete");
  if(result != BLOCKSDB_DONE) {
    LOG_EXIT();
    return result;
  }
  result = execute_simple(dbstate, "DROP TABLE blocks_to_delete");
  LOG_EXIT();
  return result;
}

BLOCKSDB_RESULT get_modcount(BlocksDbState* dbstate, int *out_modcount) {
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  sqlite3_stmt* stmt;
  if(SQLITE_OK != sqlite3_prepare_v2(dbstate->handle, "SELECT value FROM props WHERE name = 'modification_counter'",
				     -1, &stmt, NULL))
    RET_SQLITE_ERROR("Couldn't prepare query in get_modcount()");
  if(SQLITE_ROW != sqlite3_step (stmt))
    RET_SQLITE_ERROR("Unexpected step result in get_modcount()");
  *out_modcount = sqlite3_column_int(stmt, 0);
  if(SQLITE_OK != sqlite3_finalize(stmt))
    RET_SQLITE_ERROR();
  LOG_EXIT();
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT get_block_size(BlocksDbState* dbstate, int *out_block_size) {
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  sqlite3_stmt* stmt;
  if(SQLITE_OK != sqlite3_prepare_v2(dbstate->handle, "SELECT value FROM props WHERE name = 'block_size'",
				     -1, &stmt, NULL))
    RET_SQLITE_ERROR("Couldn't prepare query in get_block_size()");
  if(SQLITE_ROW != sqlite3_step (stmt))
    RET_SQLITE_ERROR("Unexpected step result in get_block_size()");
  *out_block_size = sqlite3_column_int(stmt, 0);
  if(SQLITE_OK != sqlite3_finalize(stmt))
    RET_SQLITE_ERROR();
  LOG_EXIT();
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT increment_modcount(BlocksDbState* dbstate) {
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  BLOCKSDB_RESULT result = execute_simple(dbstate, "UPDATE props SET value = value + 1 where name = 'modification_counter'");
  LOG_EXIT();
  return result;
}

static BLOCKSDB_RESULT initialize_database(BlocksDbState* dbstate, unsigned block_size) {
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);

  char *sql[] = {
    "PRAGMA main.locking_mode=NORMAL",
    "BEGIN EXCLUSIVE",
    "CREATE TABLE IF NOT EXISTS blocks (blob BLOB(16) NOT NULL, offset LONG NOT NULL, md5_short BLOB(4) NOT NULL, md5 BLOB(16) NOT NULL, row_crc INT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS rolling (value LONG NOT NULL)",
    "CREATE TABLE IF NOT EXISTS props (name TEXT PRIMARY KEY, value TEXT)",
    "INSERT OR IGNORE INTO props VALUES ('modification_counter', 0)",
    "CREATE UNIQUE INDEX IF NOT EXISTS index_offset ON blocks (blob, offset)",    
    "CREATE INDEX IF NOT EXISTS index_block_md5 ON blocks (md5_short)",    
    "\0 SENTINEL"
  };

  for(int i = 0; *sql[i] != '\0'; i++){
    const int retval = sqlite3_exec(dbstate->handle, sql[i], NULL, NULL, NULL);
    if(retval != SQLITE_OK){
      sprintf(dbstate->error_msg, "Error while initializing database (%s): %s", sql[i], sqlite3_errmsg(dbstate->handle));
      LOG_EXIT();
      return BLOCKSDB_ERR_OTHER;
    }
  }

  char sql_insert_blocksize[1024];
  sprintf(sql_insert_blocksize, "INSERT OR IGNORE INTO props VALUES ('block_size', %u)", block_size);
  int result = -1;
  result = execute_simple(dbstate, sql_insert_blocksize);
  if(result != BLOCKSDB_DONE) {
    RET_SQLITE_ERROR("Insert prop failed");
  }

  result = execute_simple(dbstate, "COMMIT");
  if(result != BLOCKSDB_DONE) {
    RET_SQLITE_ERROR("Commit failed");
  } 
  blocksdb_log("Commit successful");
  // At this point, any client caused block size error should have
  // been handled in a nice way.
  int fetched_block_size;
  result = get_block_size(dbstate, &fetched_block_size);
  if(result != BLOCKSDB_DONE)
    RET_SQLITE_ERROR("get_block_size() failed");

  if(fetched_block_size != block_size)
    RET_SQLITE_ERROR("Block size mismatch");

  LOG_EXIT();
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT init_blocksdb(const char* dbfile, int block_size, BlocksDbState** out_state){
  LOG_ENTER();
  BlocksDbState* state = (BlocksDbState*) calloc(1, sizeof(BlocksDbState));
  *out_state = state;
  const int retval = sqlite3_open(dbfile, &state->handle);
  if(retval != SQLITE_OK){
    sprintf(state->error_msg, "Error while opening database %s: %s", dbfile, sqlite3_errmsg(state->handle));
    LOG_EXIT();
    return BLOCKSDB_ERR_CORRUPT;
  }
  state->magic = 0xabcd1234;
  state->stmt = NULL;

#ifdef ENABLE_BLOCKSDB_LOGGING
  sqlite3_trace(state->handle, trace_callback, NULL);
#endif
  sqlite3_busy_timeout(state->handle, 10*60*1000);
  BLOCKSDB_RESULT result = initialize_database(state, block_size);
  LOG_EXIT();
  return result;
}

BLOCKSDB_RESULT close_blocksdb(BlocksDbState* dbstate){
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  const int retval = sqlite3_close(dbstate->handle);
  if(retval != SQLITE_OK){
    RET_SQLITE_ERROR();
  }
  free(dbstate);
  LOG_EXIT();
  return BLOCKSDB_DONE;
}


BLOCKSDB_RESULT begin_blocksdb(BlocksDbState* dbstate) {
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  BLOCKSDB_RESULT result = execute_simple(dbstate, "BEGIN");
  LOG_EXIT();
  return result;
}

BLOCKSDB_RESULT commit_blocksdb(BlocksDbState* dbstate) {
  LOG_ENTER();
  ASSERT_VALID_STATE(dbstate);
  BLOCKSDB_RESULT result = execute_simple(dbstate, "COMMIT");
  LOG_EXIT();
  return result;
}

const char* get_error_message(BlocksDbState* dbstate) {
  ASSERT_VALID_STATE(dbstate);
  dbstate->error_msg[1023] = 0;
  return dbstate->error_msg;
}
