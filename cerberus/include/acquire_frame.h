#ifndef CERBERUS_ACQUIRE_FRAME
#define CERBERUS_ACQUIRE_FRAME

#include <stdlib.h>

/**
 * @brief Acquisisce una foto RGB 640x480 e la salva in formato PPM P6.
 * @param[in] path Percorso valido e non NULL del file di uscita; le directory devono
 * gia' esistere. Un percorso relativo e' risolto dalla directory di esecuzione.
 * @return EXIT_SUCCESS (0) se acquisizione, scrittura e chiusura file riescono;
 * EXIT_FAILURE se falliscono dimensionamento, allocazione, cattura o salvataggio.
 * Il ritorno indica l'esito: non e' il descrittore di un file ne' il codice negativo della camera.
 * @note Alloca e libera internamente il buffer RGB a ogni chiamata; il chiamante
 * non deve allocarlo o liberarlo. Usa il backend camera.h e richiede una camera disponibile.
 * La chiamata e' sincrona: il chiamante attende fino al termine, incluso il salvataggio.
 * Il timeout di 1000 ms riguarda l'attesa dei frame nel backend, non l'intera chiamata.
 * Apre il file solo dopo una cattura riuscita; un file esistente viene sovrascritto.
 * Se il salvataggio fallisce, il file puo' essere parziale: la scrittura non e' atomica.
 * Stampa informazioni su stdout e diagnostiche su stderr; non termina il processo.
 */
int acquire_and_save_frame(const char *path);

#endif