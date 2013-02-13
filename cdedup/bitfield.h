#ifndef BITFIELD_H
#define BITFIELD_H

typedef struct _Bitfield {
  unsigned int size;
  unsigned int* words;
  unsigned int sentinel;
} BitField;

BitField* bf_create(const unsigned int number_of_bits);
void bf_set(BitField* bf, unsigned int bit, int value);
unsigned int bf_get(BitField* bf, unsigned int bit);
void bf_print(BitField* bf);
void bf_destroy(BitField* bf);

#endif
