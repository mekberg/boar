#include "stdlib.h"
#include "stdio.h"
#include "stdint.h"
#include "string.h"
#include "time.h"

#include "sqlite3.h"
#include "blocksdb.h"

#include "crc16.h"

#define false 0

#define RET_ERROR_OTHER(msg) {						\
    sprintf(dbstate->error_msg, msg "(%s:%u: %s)",			\
	    __FILE__, __LINE__, sqlite3_errmsg(dbstate->handle));	\
    return BLOCKSDB_ERR_OTHER;						\
  }

#define RET_ERROR_CORRUPT(msg) {					\
    sprintf(dbstate->error_msg, msg "(%s:%u: %s)",			\
	    __FILE__, __LINE__, "blocks database is corrupt");		\
    return BLOCKSDB_ERR_CORRUPT;					\
  }

#define ASSERT_VALID_STATE(dbstate) 					\
  if (dbstate->magic != 0xabcd1234) {					\
      printf("Invalid magic number at %s:%u\n", __FILE__, __LINE__);	\
      assert(false, "Invalid magic number");				\
  }

static inline void assert(int c, const char* msg){
  if(c == 0){
    printf("ASSERT FAILED: %s\n", msg);
    exit(1);
  }
}

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
  ASSERT_VALID_STATE(dbstate);
  int retval =  sqlite3_exec(dbstate->handle, sql, NULL, NULL, NULL);
  if(retval != SQLITE_OK){
    strcpy(dbstate->error_msg, sqlite3_errmsg(dbstate->handle));
    return BLOCKSDB_ERR_OTHER;
  }
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT get_rolling_init(BlocksDbState* dbstate){
  ASSERT_VALID_STATE(dbstate);
  // TODO: error if a stmt is already active
  assert(dbstate->stmt == NULL, "get_rolling_init(): Tried to create a second cursor");
  const int s = sqlite3_prepare_v2(dbstate->handle, "SELECT value FROM rolling", -1, &dbstate->stmt, NULL);
  if (s == SQLITE_OK) {
    return BLOCKSDB_DONE;
  }
  sprintf(dbstate->error_msg, 
	  "Error while initializing fetching rolling checksums: %s", 
	  sqlite3_errmsg(dbstate->handle));
  return BLOCKSDB_ERR_OTHER; // Should never get here
}

BLOCKSDB_RESULT get_rolling_next(BlocksDbState* dbstate, uint64_t *rolling) {
  ASSERT_VALID_STATE(dbstate);
  int s = sqlite3_step (dbstate->stmt);
  if (s == SQLITE_ROW) {
    *rolling = (uint64_t) sqlite3_column_int64(dbstate->stmt, 0);
    return BLOCKSDB_ROW;
  }
  else if (s == SQLITE_DONE) {
    return BLOCKSDB_DONE;
  }
  sprintf(dbstate->error_msg, 
	  "Error while fetching rolling checksums (sqlite error %d): %s", 
	  s, sqlite3_errmsg(dbstate->handle));
  return BLOCKSDB_ERR_OTHER; // Should never get here
}

BLOCKSDB_RESULT get_rolling_finish(BlocksDbState* dbstate) {
  ASSERT_VALID_STATE(dbstate);
  sqlite3_finalize(dbstate->stmt);
  dbstate->stmt = NULL;
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT add_rolling(BlocksDbState* dbstate, uint64_t rolling){
  ASSERT_VALID_STATE(dbstate);
  sqlite3_stmt* stmt;
  if(SQLITE_OK != sqlite3_prepare_v2(dbstate->handle, "INSERT INTO rolling (value) VALUES (?)",
				     -1, &stmt, NULL))
    RET_ERROR_OTHER("Couldn't prepare statement in add_rolling()");
  if(SQLITE_OK != sqlite3_bind_int64(stmt, 1, (sqlite3_int64) rolling))
    RET_ERROR_OTHER();
  if(SQLITE_DONE != sqlite3_step(stmt)) {
    RET_ERROR_OTHER("Unexpected step result in add_rolling()");
  }
  if(SQLITE_OK != sqlite3_finalize(stmt))
    RET_ERROR_OTHER();  
  return BLOCKSDB_DONE;
}


BLOCKSDB_RESULT add_block(BlocksDbState* dbstate, const char* blob, uint64_t offset, const char* md5){
  ASSERT_VALID_STATE(dbstate);
  //const char* md5_row = block_row_checksum(blob, offset, md5);
  if(! is_md5sum(blob)) {
    sprintf(dbstate->error_msg, "add_block(): Not a valid blob name: %s", blob);    
    return BLOCKSDB_ERR_OTHER;
  }
  if(! is_md5sum(md5)) {
    sprintf(dbstate->error_msg, "add_block(): Not a valid md5 sum: %s", md5);    
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
    RET_ERROR_OTHER("Error while preparing add_block()");
  }
  
  if(SQLITE_OK != sqlite3_bind_blob(stmt, 1, packed_blob, 16, SQLITE_STATIC)) 
    RET_ERROR_OTHER();
  if(SQLITE_OK != sqlite3_bind_int64(stmt, 2, (int64_t) offset))
    RET_ERROR_OTHER();
  if(SQLITE_OK != sqlite3_bind_blob(stmt, 3, packed_md5, 4, SQLITE_STATIC))
    RET_ERROR_OTHER();
  if(SQLITE_OK != sqlite3_bind_blob(stmt, 4, packed_md5, 16, SQLITE_STATIC))
    RET_ERROR_OTHER();
  if(SQLITE_OK != sqlite3_bind_int(stmt, 5, row_crc))
    RET_ERROR_OTHER();

  if(SQLITE_DONE != sqlite3_step(stmt))
    RET_ERROR_OTHER("Error while inserting new block");

  if(SQLITE_OK != sqlite3_finalize(stmt))
    RET_ERROR_OTHER();
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT get_blocks_init(BlocksDbState* dbstate, char* md5, int limit){
  ASSERT_VALID_STATE(dbstate);
  if(! is_md5sum(md5)) {
    sprintf(dbstate->error_msg, "get_blocks_init(): Not a valid md5 sum: %s", md5);    
    return BLOCKSDB_ERR_OTHER;
  }
  int retval;
  retval = sqlite3_prepare_v2(dbstate->handle, "SELECT blocks.blob, blocks.offset, blocks.row_crc, blocks.md5 FROM blocks WHERE md5_short = ? AND md5 = ? LIMIT ?",
                              -1, &dbstate->stmt, NULL);
  if(retval != SQLITE_OK){
    RET_ERROR_OTHER("get_blocks_init() prepare failed");
  }

  char packed_md5[16];
  pack_md5(md5, packed_md5);

  if(SQLITE_OK != sqlite3_bind_blob(dbstate->stmt, 1, packed_md5, 4, SQLITE_TRANSIENT))
    RET_ERROR_OTHER();
  if(SQLITE_OK != sqlite3_bind_blob(dbstate->stmt, 2, packed_md5, 16, SQLITE_TRANSIENT))
    RET_ERROR_OTHER();
  if(SQLITE_OK != sqlite3_bind_int(dbstate->stmt, 3, limit))
    RET_ERROR_OTHER();
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT get_blocks_next(BlocksDbState* dbstate, char* blob, uint64_t* offset) {
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
      return BLOCKSDB_ERR_CORRUPT;
    }

    return BLOCKSDB_ROW;
  }
  else if (s == SQLITE_DONE) {
    return BLOCKSDB_DONE;
  }
  assert(false, "Unexpected result in get_all_rolling_next");
  return BLOCKSDB_ERR_OTHER; // should never get here
}

BLOCKSDB_RESULT get_blocks_finish(BlocksDbState* dbstate) {
  ASSERT_VALID_STATE(dbstate);
  assert(dbstate->stmt != NULL, "Tried to call get_blocks_finish() with no active cursor");
  if(SQLITE_OK != sqlite3_finalize(dbstate->stmt))
    RET_ERROR_OTHER();
  dbstate->stmt = NULL;
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT delete_blocks_init(BlocksDbState* dbstate){
  ASSERT_VALID_STATE(dbstate);
  return execute_simple(dbstate, "CREATE TEMPORARY TABLE blocks_to_delete (blob CHAR(16) PRIMARY KEY)");
}

BLOCKSDB_RESULT delete_blocks_add(BlocksDbState* dbstate, char* blob){
  ASSERT_VALID_STATE(dbstate);
  if(! is_md5sum(blob)) {
    sprintf(dbstate->error_msg, "delete_blocks_add(): Not a valid blob name: %s", blob);
    return BLOCKSDB_ERR_OTHER;
  }
  char packed_blob[16];
  pack_md5(blob, packed_blob);
  sqlite3_stmt* stmt;

  if(SQLITE_OK != sqlite3_prepare_v2(dbstate->handle, "INSERT OR IGNORE INTO blocks_to_delete (blob) VALUES (?)",
				     -1, &stmt, NULL)) {
    RET_ERROR_OTHER("Error while preparing delete_blocks_add()");
  }
  if(SQLITE_OK != sqlite3_bind_blob(stmt, 1, packed_blob, 16, SQLITE_STATIC))
    RET_ERROR_OTHER();

  if(SQLITE_DONE != sqlite3_step(stmt))
    RET_ERROR_OTHER("Error while adding blob to list of blocks to delete");

  if(SQLITE_OK != sqlite3_finalize(stmt))
    RET_ERROR_OTHER();
  
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT delete_blocks_finish(BlocksDbState* dbstate){
  ASSERT_VALID_STATE(dbstate);
  BLOCKSDB_RESULT result = execute_simple(dbstate, "DELETE FROM blocks WHERE blocks.blob IN blocks_to_delete");
  if(result != BLOCKSDB_DONE) {
    return result;
  }
  return execute_simple(dbstate, "DROP TABLE blocks_to_delete");
}

BLOCKSDB_RESULT get_modcount(BlocksDbState* dbstate, int *out_modcount) {
  ASSERT_VALID_STATE(dbstate);
  sqlite3_stmt* stmt;
  if(SQLITE_OK != sqlite3_prepare_v2(dbstate->handle, "SELECT value FROM props WHERE name = 'modification_counter'",
				     -1, &stmt, NULL))
    RET_ERROR_OTHER("Couldn't prepare query in get_modcount()");
  if(SQLITE_ROW != sqlite3_step (stmt))
    RET_ERROR_OTHER("Unexpected step result in get_modcount()");
  *out_modcount = sqlite3_column_int(stmt, 0);
  if(SQLITE_OK != sqlite3_finalize(stmt))
    RET_ERROR_OTHER();
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT get_block_size(BlocksDbState* dbstate, int *out_block_size) {
  ASSERT_VALID_STATE(dbstate);
  sqlite3_stmt* stmt;
  if(SQLITE_OK != sqlite3_prepare_v2(dbstate->handle, "SELECT value FROM props WHERE name = 'block_size'",
				     -1, &stmt, NULL))
    RET_ERROR_OTHER("Couldn't prepare query in get_block_size()");
  if(SQLITE_ROW != sqlite3_step (stmt))
    RET_ERROR_OTHER("Unexpected step result in get_block_size()");
  *out_block_size = sqlite3_column_int(stmt, 0);
  if(SQLITE_OK != sqlite3_finalize(stmt))
    RET_ERROR_OTHER();
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT increment_modcount(BlocksDbState* dbstate) {
  ASSERT_VALID_STATE(dbstate);
  return execute_simple(dbstate, "UPDATE props SET value = value + 1 where name = 'modification_counter'");
}

static BLOCKSDB_RESULT initialize_database(BlocksDbState* dbstate, unsigned block_size) {
  ASSERT_VALID_STATE(dbstate);
  char *sql[] = {
    //PRAGMA main.journal_mode=WAL;");
    //PRAGMA main.page_size = 4096;");
    //PRAGMA main.cache_size=10000;");
    "PRAGMA main.locking_mode=NORMAL",
    //"PRAGMA main.synchronous=OFF;");
    //main.journal_mode=DELETE;");
    
    "BEGIN",
    "CREATE TABLE IF NOT EXISTS blocks (blob BLOB(16) NOT NULL, offset LONG NOT NULL, md5_short BLOB(4) NOT NULL, md5 BLOB(16) NOT NULL, row_crc INT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS rolling (value LONG NOT NULL)",
    "CREATE TABLE IF NOT EXISTS props (name TEXT PRIMARY KEY, value TEXT)",
    "INSERT OR IGNORE INTO props VALUES ('modification_counter', 0)",
    //"CREATE UNIQUE INDEX IF NOT EXISTS index_rolling ON rolling (value)",
    "CREATE UNIQUE INDEX IF NOT EXISTS index_offset ON blocks (blob, offset)",    
    "CREATE INDEX IF NOT EXISTS index_block_md5 ON blocks (md5_short)",    
    //"CREATE INDEX IF NOT EXISTS index_md5_long ON blocks (md5)",    
    "COMMIT",
    
    "\0 SENTINEL"
  };

  for(int i = 0; *sql[i] != '\0'; i++){
    const int retval = sqlite3_exec(dbstate->handle, sql[i], NULL, NULL, NULL);
    if(retval != SQLITE_OK){
      sprintf(dbstate->error_msg, "Error while initializing database: %s", sqlite3_errmsg(dbstate->handle));
      return BLOCKSDB_ERR_OTHER;
    }
  }

  char sql_insert_blocksize[1024];
  sprintf(sql_insert_blocksize, "INSERT OR IGNORE INTO props VALUES ('block_size', %u)", block_size);
  int result = -1;
  result = execute_simple(dbstate, sql_insert_blocksize);
  if(result != BLOCKSDB_DONE)
    return result;

  // At this point, any client caused block size error should have
  // been handled in a nice way.
  int fetched_block_size;
  result = get_block_size(dbstate, &fetched_block_size);
  if(result != BLOCKSDB_DONE)
    return result;

  assert(fetched_block_size == block_size, "Block size mismatch");
  
  return BLOCKSDB_DONE;
}

#include "unistd.h"
#include "sys/time.h"
void trace_callback( void* udp, const char* sql ) { 
  static FILE* log = NULL;
  if(log == NULL)
    log = fopen("/tmp/log.txt", "a");
  struct timeval  tv;
  gettimeofday(&tv, NULL);
  long long time_in_mill = 
    (tv.tv_sec) * 1000000 + (tv.tv_usec)  - 1366644831735000ll;
  
  fprintf(log, "%lld {PID %d} [%s]\n", time_in_mill, getpid(), sql); 
} 

BLOCKSDB_RESULT init_blocksdb(const char* dbfile, int block_size, BlocksDbState** out_state){
  //printf("Opening %s\n", dbfile);
  BlocksDbState* state = (BlocksDbState*) calloc(1, sizeof(BlocksDbState));
  *out_state = state;
  const int retval = sqlite3_open(dbfile, &state->handle);
  if(retval != SQLITE_OK){
    sprintf(state->error_msg, "Error while opening database %s: %s", dbfile, sqlite3_errmsg(state->handle));
    return BLOCKSDB_ERR_CORRUPT;
  }
  state->magic = 0xabcd1234;
  state->stmt = NULL;

  sqlite3_trace(state->handle, trace_callback, NULL);
  return initialize_database(state, block_size);
}

BLOCKSDB_RESULT close_blocksdb(BlocksDbState* dbstate){
  ASSERT_VALID_STATE(dbstate);
  const int retval = sqlite3_close(dbstate->handle);
  if(retval != SQLITE_OK){
    RET_ERROR_OTHER();
  }
  free(dbstate);
  return BLOCKSDB_DONE;
}


BLOCKSDB_RESULT begin_blocksdb(BlocksDbState* dbstate) {
  ASSERT_VALID_STATE(dbstate);
  return execute_simple(dbstate, "BEGIN");
}

BLOCKSDB_RESULT commit_blocksdb(BlocksDbState* dbstate) {
  ASSERT_VALID_STATE(dbstate);
  return execute_simple(dbstate, "COMMIT");
}

const char* get_error_message(BlocksDbState* dbstate) {
  ASSERT_VALID_STATE(dbstate);
  dbstate->error_msg[1023] = 0;
  return dbstate->error_msg;
}

/*

int main() {
  BlocksDbState* state;
  init_blocksdb("/tmp/blocksdb-test", 65536, &state);
  close_blocksdb(state);
}

*/
