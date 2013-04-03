#include "stdlib.h"
#include "stdio.h"
#include "stdint.h"
#include "string.h"
#include "time.h"

#include "sqlite3.h"
#include "blocksdb.h"

#define false 0

#define CHECKED_SQLITE(C)   { int retval = C; \
  if(retval != SQLITE_OK){                           \
    printf( "In %s line %u: SQLITE call failed: %s\n", __func__, __LINE__, sqlite3_errmsg(dbstate->handle) ); \
    assert(false, "Sqlite call failed"); \
  } \
  }

#define CHECKED_SQLITE_STEP(C)   { int retval = C; \
  if(retval != SQLITE_DONE){                           \
    printf( "In %s line %u: SQLITE STEP didn't complete: %s\n", __func__, __LINE__, sqlite3_errmsg(dbstate->handle) ); \
    assert(false, "Sqlite step failed"); \
  } \
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

void execute_simple(BlocksDbState* dbstate, char* sql) {
  char* errmsg;
  int retval =  sqlite3_exec(dbstate->handle, sql, NULL, NULL, &errmsg);
  if(retval != SQLITE_OK){
    assert(false, errmsg);
  }
  assert(retval == SQLITE_OK, errmsg);
}

BLOCKSDB_RESULT get_rolling_init(BlocksDbState* dbstate){
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
  int s = sqlite3_step (dbstate->stmt);
  if (s == SQLITE_ROW) {
    *rolling = (uint64_t) sqlite3_column_int64(dbstate->stmt, 0);
    return BLOCKSDB_ROW;
  }
  else if (s == SQLITE_DONE) {
    return BLOCKSDB_DONE;
  }
  sprintf(dbstate->error_msg, 
	  "Error while fetching rolling checksums: %s", 
	  sqlite3_errmsg(dbstate->handle));
  return BLOCKSDB_ERR_OTHER; // Should never get here
}

BLOCKSDB_RESULT get_rolling_finish(BlocksDbState* dbstate) {
  sqlite3_finalize(dbstate->stmt);
  return BLOCKSDB_DONE;
}

void add_rolling(BlocksDbState* dbstate, uint64_t rolling){
  sqlite3_stmt* stmt;
  CHECKED_SQLITE(sqlite3_prepare_v2(dbstate->handle, "INSERT INTO rolling (value) VALUES (?)",
				    -1, &stmt, NULL));
  CHECKED_SQLITE(sqlite3_bind_int64(stmt, 1, (sqlite3_int64) rolling));
  CHECKED_SQLITE_STEP(sqlite3_step(stmt));
  sqlite3_finalize(stmt);
  
}

void add_block(BlocksDbState* dbstate, const char* blob, uint32_t offset, const char* md5){
  //const char* md5_row = block_row_checksum(blob, offset, md5);
  const char* md5_row = "0000";
  char packed_md5[16];
  pack_md5(md5, packed_md5);
  char packed_blob[16];
  pack_md5(blob, packed_blob);
  sqlite3_stmt* stmt;

  CHECKED_SQLITE(sqlite3_prepare_v2(dbstate->handle, "INSERT OR IGNORE INTO blocks (blob, offset, md5_short, md5, row_md5) VALUES (?, ?, ?, ?, ?)",
				    -1, &stmt, NULL));
  sqlite3_bind_blob(stmt, 1, packed_blob, 16, SQLITE_STATIC);
  sqlite3_bind_int(stmt, 2, offset);
  sqlite3_bind_blob(stmt, 3, packed_md5, 4, SQLITE_STATIC);
  sqlite3_bind_blob(stmt, 4, packed_md5, 16, SQLITE_STATIC);
  sqlite3_bind_blob(stmt, 5, md5_row, 32, SQLITE_STATIC);
  CHECKED_SQLITE_STEP(sqlite3_step(stmt));
  sqlite3_finalize(stmt);
}

sqlite3_stmt* get_blocks_init(BlocksDbState* dbstate, char* md5, int limit){
  sqlite3_stmt* stmt;
  int retval;
  retval = sqlite3_prepare_v2(dbstate->handle, "SELECT blocks.blob, blocks.offset, blocks.row_md5 FROM blocks WHERE md5_short = ? AND md5 = ? LIMIT ?",
                              -1, &stmt, NULL);
  if(retval != SQLITE_OK){
    printf( "could not prepare statement: %s\n", sqlite3_errmsg(dbstate->handle) );
    assert(false, "fail prepare");
  }
  char packed_md5[16];
  pack_md5(md5, packed_md5);
  sqlite3_bind_blob(stmt, 1, packed_md5, 4, SQLITE_TRANSIENT);
  sqlite3_bind_blob(stmt, 2, packed_md5, 16, SQLITE_TRANSIENT);
  sqlite3_bind_int(stmt, 3, limit);
  return stmt;
}

int get_blocks_next(sqlite3_stmt* stmt, char* blob, uint32_t* offset, char* row_md5) {
  int s = sqlite3_step (stmt);
  if (s == SQLITE_ROW) {
    const char* blob_col = (const char*) sqlite3_column_text(stmt, 0);
    const int blob_col_length = sqlite3_column_bytes(stmt, 0);
    assert(blob_col_length == 16, "Unexpected column length in get_blocks_next()");
    unpack_md5(blob_col, blob);

    *offset = sqlite3_column_int(stmt, 1);

    const char* row_md5_col = (const char*) sqlite3_column_text(stmt, 2);
    const int row_md5_col_length = sqlite3_column_bytes(stmt, 2);
    strncpy(row_md5, row_md5_col, row_md5_col_length);

    return 1;
  }
  else if (s == SQLITE_DONE) {
    return 0;
  }
  assert(false, "Unexpected result in get_all_rolling_next");
  return 0; // should never get here
}

void get_blocks_finish(sqlite3_stmt* stmt) {
  sqlite3_finalize(stmt);
}

int get_modcount(BlocksDbState* dbstate) {
  sqlite3_stmt* stmt;
  CHECKED_SQLITE(sqlite3_prepare_v2(dbstate->handle, "SELECT value FROM props WHERE name = 'modification_counter'",
				    -1, &stmt, NULL));
  const int s = sqlite3_step (stmt);
  assert(s == SQLITE_ROW, "Unexpected result from select");
  const int result = sqlite3_column_int(stmt, 0);
  sqlite3_finalize(stmt);
  return result;  
}

void increment_modcount(BlocksDbState* dbstate) {
  execute_simple(dbstate, "UPDATE props SET value = value + 1 where name = 'modification_counter'");
}

static BLOCKSDB_RESULT initialize_database(BlocksDbState* dbstate) {
  char *sql[] = {
    //PRAGMA main.journal_mode=WAL;");
    //PRAGMA main.page_size = 4096;");
    //PRAGMA main.cache_size=10000;");
    "PRAGMA main.locking_mode=NORMAL",
    //"PRAGMA main.synchronous=OFF;");
    //main.journal_mode=DELETE;");
    
    "BEGIN",
    "CREATE TABLE IF NOT EXISTS blocks (blob BLOB(16) NOT NULL, offset LONG NOT NULL, md5_short BLOB(4) NOT NULL, md5 BLOB(16) NOT NULL, row_md5 char(32))",
    "CREATE TABLE IF NOT EXISTS rolling (value LONG NOT NULL)",
    "CREATE TABLE IF NOT EXISTS props (name TEXT PRIMARY KEY, value TEXT)",
    "INSERT OR IGNORE INTO props VALUES ('block_size', 65536)",
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
  return BLOCKSDB_DONE;
}

BLOCKSDB_RESULT init_blocksdb(const char* dbfile, BlocksDbState** out_state){
  //printf("Opening %s\n", dbfile);
  BlocksDbState* state = (BlocksDbState*) calloc(1, sizeof(BlocksDbState));
  *out_state = state;
  const int retval = sqlite3_open(dbfile, &state->handle);
  if(retval != SQLITE_OK){
    sprintf(state->error_msg, "Error while opening database %s: %s", dbfile, sqlite3_errmsg(state->handle));
    return BLOCKSDB_ERR_CORRUPT;
  }
  state->magic = 0xabcdabcd;
  return initialize_database(state);
}


void begin_blocksdb(BlocksDbState* dbstate) {
  execute_simple(dbstate, "BEGIN");
}

int commit_blocksdb(BlocksDbState* dbstate) {
  const int modcount = get_modcount(dbstate);
  execute_simple(dbstate, "COMMIT");
  return modcount;
}

const char* get_error_message(BlocksDbState* dbstate) {
  dbstate->error_msg[1023] = 0;
  return dbstate->error_msg;
}
