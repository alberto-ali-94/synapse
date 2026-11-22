#ifndef IO_H
#define IO_H
#include <stddef.h>

typedef struct {
    char buf[5];
    size_t used;
    int discarding;
} input_state;


/**
 * @brief Stampa su stdout il logo testuale del Cerbero e il nome CERBERUS.
 * @note Mantiene spazi e righe del disegno, poi esegue fflush(stdout).
 * Richiede un terminale UTF-8 con font monospaziato e almeno 71 colonne.
 * Non cancella lo schermo e non viene chiamata automaticamente.
 * Non riceve parametri e non restituisce un esito degli errori di output.
 */
void print_cerberus_logo(void);

void print_menu(void);
void init_input(input_state *state);
int read_input(input_state *state, int *output);
int read_integer(int *p);
int str_to_int(char *str, int *result);
void clear_screen(void);

#endif