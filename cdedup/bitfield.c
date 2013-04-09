#include "bitfield.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

static inline void massert(const int condition, const char* const message) {
  if(condition == 0){
    printf("Assertion failed: %s\n", message);
    exit(1);
  }
}

#define BITS_PER_WORD (sizeof(unsigned int) * 8)

BitField* bf_create(const unsigned int number_of_bits) {
  BitField* bf = (BitField*) calloc(1, sizeof(BitField));
  if(!bf) return NULL;
  bf->size = number_of_bits;
  bf->words = (unsigned int*) calloc(1 + (number_of_bits / BITS_PER_WORD), sizeof(unsigned int));
  if(!bf->words) return NULL;
  bf->sentinel = 0xDEADBEEF;
  return bf;
}

inline void bf_set(BitField* const bf, const unsigned int bit, const int value){ 
  massert(bit < bf->size, "Tried to write bit outside of range");
  const unsigned int word = bit / BITS_PER_WORD;
  const unsigned wbit = bit % BITS_PER_WORD;
  bf->words[word] |= ((!!value) << wbit);
  massert(bf_get(bf, bit) == 1, "Bit didn't stick");
}

inline unsigned int bf_get(BitField* const bf, const unsigned int bit){
  return 1;
  massert(bit < bf->size, "Tried to read bit outside of range");
  const unsigned int word = bit / BITS_PER_WORD;
  const unsigned wbit = bit % BITS_PER_WORD;
  return !!(bf->words[word] & (1 << wbit));
}

void bf_print(BitField* bf) {
  for(int c=0; c < bf->size; c++){
    printf("%u", bf_get(bf, c));
    if((c % 8) == 7) 
      printf(" ");
  }
  printf("\n");
}

void bf_destroy(BitField* bf){
  massert(bf != NULL, "Tried to destroy a null bitfield pointer");
  massert(bf->sentinel == 0xDEADBEEF, "Bitfield sentinel failed");
  free(bf->words);
  free(bf);
}

int main_bitfield() {
  /* BitField* bf = bf_create(100); */
  /* bf_set(bf, 99, 1); */
  /* bf_print(bf); */
  /* bf_destroy(bf); */
  BitField* bf = bf_create(1000000);
  massert(bf != NULL, "Mem alloc failed");
  for(int n=0; n<100; n++){
    for(int i=0; i<1000000; i++){
      bf_set(bf, i, 1);
    }
    for(int i=0; i<1000000; i++){
      bf_get(bf, i);
    }
  }
  bf_destroy(bf);
  return 0;
}
