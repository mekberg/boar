#include "stdlib.h"
#include "stdio.h"
#include "stdint.h"
#include "string.h"
#include "time.h"

#include "blocksdb.h"

#include "sqlite3.h"

#define false 0

#define CHECKED_SQLITE(C)   { int retval = C; \
  if(retval != SQLITE_OK){                           \
    printf( "In %s line %u: SQLITE call failed: %s\n", __func__, __LINE__, sqlite3_errmsg(handle) ); \
    assert(false, "Sqlite call failed"); \
  } \
  }

#define CHECKED_SQLITE_STEP(C)   { int retval = C; \
  if(retval != SQLITE_DONE){                           \
    printf( "In %s line %u: SQLITE STEP didn't complete: %s\n", __func__, __LINE__, sqlite3_errmsg(handle) ); \
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

/*
int main() {
  const char* md5_text = "d41d8cd98f00b204e9800998ecf8427e";
  unsigned char md5_bin[16];
  char md5_text_2[33];
  md5_text_2[32] = 0;
  
  hex2bin(md5_text, 32, md5_bin);
  bin2hex(md5_bin, 16, md5_text_2);
  printf("%s\n", md5_text_2);
}
*/


void execute_simple(sqlite3 *handle, char* sql) {
  char* errmsg;
  int retval =  sqlite3_exec(handle, sql, NULL, NULL, &errmsg);
  if(retval != SQLITE_OK){
    assert(false, errmsg);
  }
  assert(retval == SQLITE_OK, errmsg);
}

sqlite3_stmt* get_rolling_init(sqlite3 *handle){
  sqlite3_stmt* stmt;
  CHECKED_SQLITE(sqlite3_prepare_v2(handle, "SELECT value FROM rolling", -1, &stmt, NULL));
  return stmt;
}

int get_rolling_next(sqlite3_stmt* stmt, uint64_t *rolling) {
  int s = sqlite3_step (stmt);
  if (s == SQLITE_ROW) {
    *rolling = (uint64_t) sqlite3_column_int64(stmt, 0);
    return 1;
  }
  else if (s == SQLITE_DONE) {
    return 0;
  }
  assert(false, "Unexpected result in get_all_rolling_next");
  return 0; // Should never get here
}

void get_rolling_finish(sqlite3_stmt* stmt) {
  sqlite3_finalize(stmt);
}

void add_rolling(sqlite3 *handle, uint64_t rolling){
  sqlite3_stmt* stmt;
  CHECKED_SQLITE(sqlite3_prepare_v2(handle, "INSERT INTO rolling (value) VALUES (?)",
				    -1, &stmt, NULL));
  CHECKED_SQLITE(sqlite3_bind_int64(stmt, 1, (sqlite3_int64) rolling));
  CHECKED_SQLITE_STEP(sqlite3_step(stmt));
  sqlite3_finalize(stmt);
  
}

void add_block(sqlite3 *handle, const char* blob, uint32_t offset, const char* md5){
  //const char* md5_row = block_row_checksum(blob, offset, md5);
  const char* md5_row = "0000";
  char packed_md5[16];
  pack_md5(md5, packed_md5);
  char packed_blob[16];
  pack_md5(blob, packed_blob);
  sqlite3_stmt* stmt;

  CHECKED_SQLITE(sqlite3_prepare_v2(handle, "INSERT OR IGNORE INTO blocks (blob, offset, md5_short, md5, row_md5) VALUES (?, ?, ?, ?, ?)",
				    -1, &stmt, NULL));
  sqlite3_bind_blob(stmt, 1, packed_blob, 16, SQLITE_STATIC);
  sqlite3_bind_int(stmt, 2, offset);
  sqlite3_bind_blob(stmt, 3, packed_md5, 4, SQLITE_STATIC);
  sqlite3_bind_blob(stmt, 4, packed_md5, 16, SQLITE_STATIC);
  sqlite3_bind_blob(stmt, 5, md5_row, 32, SQLITE_STATIC);
  CHECKED_SQLITE_STEP(sqlite3_step(stmt));
  sqlite3_finalize(stmt);
}

sqlite3_stmt* get_blocks_init(sqlite3 *handle, char* md5, int limit){
  sqlite3_stmt* stmt;
  int retval;
  retval = sqlite3_prepare_v2(handle, "SELECT blocks.blob, blocks.offset, blocks.row_md5 FROM blocks WHERE md5_short = ? AND md5 = ? LIMIT ?",
                              -1, &stmt, NULL);
  if(retval != SQLITE_OK){
    printf( "could not prepare statement: %s\n", sqlite3_errmsg(handle) );
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

int get_modcount(sqlite3 *handle) {
  sqlite3_stmt* stmt;
  CHECKED_SQLITE(sqlite3_prepare_v2(handle, "SELECT value FROM props WHERE name = 'modification_counter'",
				    -1, &stmt, NULL));
  const int s = sqlite3_step (stmt);
  assert(s == SQLITE_ROW, "Unexpected result from select");
  const int result = sqlite3_column_int(stmt, 0);
  sqlite3_finalize(stmt);
  return result;  
}

void increment_modcount(sqlite3 *handle) {
  execute_simple(handle, "UPDATE props SET value = value + 1 where name = 'modification_counter'");
}

static void initialize_database(sqlite3 *handle) {
  //execute_simple(handle, "PRAGMA main.journal_mode=WAL;");
  //execute_simple(handle, "PRAGMA main.page_size = 4096;");
  //execute_simple(handle, "PRAGMA main.cache_size=10000;");
  execute_simple(handle, "PRAGMA main.locking_mode=NORMAL;");
  //execute_simple(handle, "PRAGMA main.synchronous=OFF;");
  //execute_simple(handle, "PRAGMA main.journal_mode=DELETE;");

  begin_blocksdb(handle);
  execute_simple(handle, "CREATE TABLE IF NOT EXISTS blocks (blob BLOB(16) NOT NULL, offset LONG NOT NULL, md5_short BLOB(4) NOT NULL, md5 BLOB(16) NOT NULL, row_md5 char(32))");
  execute_simple(handle, "CREATE TABLE IF NOT EXISTS rolling (value LONG NOT NULL)");
  execute_simple(handle, "CREATE TABLE IF NOT EXISTS props (name TEXT PRIMARY KEY, value TEXT)");
  execute_simple(handle, "INSERT OR IGNORE INTO props VALUES ('block_size', 65536)");
  execute_simple(handle, "INSERT OR IGNORE INTO props VALUES ('modification_counter', 0)");
  //execute_simple(handle, "CREATE UNIQUE INDEX IF NOT EXISTS index_rolling ON rolling (value)");
  execute_simple(handle, "CREATE UNIQUE INDEX IF NOT EXISTS index_offset ON blocks (blob, offset)");    
  execute_simple(handle, "CREATE INDEX IF NOT EXISTS index_block_md5 ON blocks (md5_short)");    
  //execute_simple(handle, "CREATE INDEX IF NOT EXISTS index_md5_long ON blocks (md5)");    
  commit_blocksdb(handle);
}

sqlite3* init_blocksdb(const char* dbfile){
  //printf("Opening %s\n", dbfile);
  sqlite3 *handle;
  int retval;
  retval = sqlite3_open(dbfile, &handle);
  assert(retval == SQLITE_OK, "Couldn't open db");
  initialize_database(handle);

  /*
  retval = sqlite3_close(handle);
  assert(retval == SQLITE_OK, "Couldn't close db");
  sqlite3_open(dbfile, &handle);
  */

  return handle;
}


void begin_blocksdb(sqlite3 *handle) {
  execute_simple(handle, "BEGIN");
}

int commit_blocksdb(sqlite3 *handle) {
  const int modcount = get_modcount(handle);
  execute_simple(handle, "COMMIT");
  return modcount;
}

