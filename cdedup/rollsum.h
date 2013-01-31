#ifndef ROLLSUM_H
#define ROLLSUM_H

#define WINDOW_SIZE 4

typedef struct _Rollsum {
  unsigned long count;               /* count of bytes included in sum */
  unsigned long s1;                  /* s1 part of sum */
  unsigned long s2;                  /* s2 part of sum */
} Rollsum;

typedef struct _RollingState {
  Rollsum sum;
  int size;
  char cbuf[WINDOW_SIZE+1]; // Circular buffer
  int ps; // Start position for circular buffer
  int pe; // End position for circular buffer (next empty position)
} RollingState;

RollingState init_rolling();
int is_full(RollingState* state);
int is_empty(RollingState* state);
int push_rolling(RollingState* state, unsigned char c_add);

#endif
