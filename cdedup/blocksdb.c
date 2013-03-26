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
    printf( "SQLITE call failed: %s\n", sqlite3_errmsg(handle) ); \
    assert(false, "Sqlite call failed"); \
  } \
  }

static inline void assert(int c, const char* msg){
  if(c == 0){
    printf("ASSERT FAILED: %s\n", msg);
    exit(1);
  }
}

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
  //int retval;
  //retval = sqlite3_prepare_v2(handle, "SELECT value FROM rolling",
  //                            -1, &stmt, NULL);  
  //assert(retval == SQLITE_OK, "fail");
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
  int retval;
  CHECKED_SQLITE(sqlite3_prepare_v2(handle, "INSERT INTO rolling (value) VALUES (?)",
				    -1, &stmt, NULL));
  CHECKED_SQLITE(sqlite3_bind_int64(stmt, 1, (sqlite3_int64) rolling));
  retval = sqlite3_step(stmt);
  assert(retval == SQLITE_DONE, "Step didn't finish");
  sqlite3_finalize(stmt);
}



void add_block(sqlite3 *handle, const char* blob, uint32_t offset, const char* md5){
  //const char* md5_row = block_row_checksum(blob, offset, md5);
  const char* md5_row = "00000000000000000000000000000000";
  sqlite3_stmt* stmt;
  int retval;
  retval = sqlite3_prepare_v2(handle, "INSERT INTO blocks (blob, offset, md5_short, md5, row_md5) VALUES (?, ?, ?, ?, ?)",
			      -1, &stmt, NULL);
  assert(retval == SQLITE_OK, "Error while preparing");
  sqlite3_bind_blob(stmt, 1, blob, 32, SQLITE_STATIC);
  sqlite3_bind_int(stmt, 2, offset);
  sqlite3_bind_blob(stmt, 3, md5, 4, SQLITE_STATIC);
  sqlite3_bind_blob(stmt, 4, md5, 32, SQLITE_STATIC);
  sqlite3_bind_blob(stmt, 5, md5_row, 32, SQLITE_STATIC);
  retval = sqlite3_step(stmt);
  sqlite3_finalize(stmt);
}

sqlite3_stmt* get_blocks_init(sqlite3 *handle, char* md5, int limit){
  sqlite3_stmt* stmt;
  int retval;
  retval = sqlite3_prepare_v2(handle, "SELECT blob, offset, row_md5 FROM blocks WHERE md5_short = ? and md5 = ? LIMIT ?",
                              -1, &stmt, NULL);
  if(retval != SQLITE_OK){
    printf( "could not prepare statemnt: %s\n", sqlite3_errmsg(handle) );
    assert(false, "fail prepare");
  }
  sqlite3_bind_blob(stmt, 1, md5, 4, SQLITE_TRANSIENT);
  sqlite3_bind_blob(stmt, 2, md5, 32, SQLITE_TRANSIENT);
  sqlite3_bind_int(stmt, 3, limit);
  return stmt;
}

int get_blocks_next(sqlite3_stmt* stmt, char* blob, uint32_t* offset, char* row_md5) {
  int s = sqlite3_step (stmt);
  if (s == SQLITE_ROW) {
    const char* blob_col = (const char*) sqlite3_column_text(stmt, 0);
    const int blob_col_length = sqlite3_column_bytes(stmt, 0);
    strncpy(blob, blob_col, blob_col_length);

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

static void initialize_database(sqlite3 *handle) {
  //execute_simple(handle, "PRAGMA main.page_size = 4096;");
  //execute_simple(handle, "PRAGMA main.cache_size=10000;");
  execute_simple(handle, "PRAGMA main.locking_mode=EXCLUSIVE;");
  execute_simple(handle, "PRAGMA main.synchronous=OFF;");
  execute_simple(handle, "PRAGMA main.journal_mode=DELETE;");
  //execute_simple(handle, "PRAGMA main.journal_mode=WAL;");

  execute_simple(handle, "CREATE TABLE IF NOT EXISTS blocks (blob char(32) NOT NULL, offset long NOT NULL, md5_short char(4) NOT NULL, md5 char(32) NOT NULL, row_md5 char(32))");
  execute_simple(handle, "CREATE TABLE IF NOT EXISTS rolling (value LONG NOT NULL)");
  execute_simple(handle, "CREATE TABLE IF NOT EXISTS props (name TEXT PRIMARY KEY, value TEXT)");
  execute_simple(handle, "INSERT OR IGNORE INTO props VALUES ('block_size', 65536)");
  //execute_simple(handle, "CREATE UNIQUE INDEX IF NOT EXISTS index_rolling ON rolling (value)");
  execute_simple(handle, "CREATE INDEX IF NOT EXISTS index_md5 ON blocks (md5_short)");
}

sqlite3* init_blocksdb(const char* dbfile){
  sqlite3 *handle;
  int retval;
  retval = sqlite3_open(dbfile, &handle);
  assert(retval == SQLITE_OK, "Couldn't open db");

  initialize_database(handle);

  return handle;
}


void begin_blocksdb(sqlite3 *handle) {
  execute_simple(handle, "BEGIN");
}

void commit_blocksdb(sqlite3 *handle) {
  execute_simple(handle, "COMMIT");
}

