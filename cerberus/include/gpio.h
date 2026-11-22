#ifndef GPIO_H
#define GPIO_H

#include <stdint.h>
#include <linux/gpio.h>

/**
 * @brief Apre /dev/gpiochip0 e legge le informazioni del controller GPIO.
 * @param[out] info Struttura valida in cui il kernel scrive nome, etichetta e numero di linee.
 * @return Descrittore del controller (>= 0) su successo; -1 su errore.
 * @note Stampa descrittore e informazioni su stdout. Non richiede ancora alcuna linea.
 * Il chiamante deve chiudere il descrittore restituito con close_fd().
 * Se la lettura delle informazioni fallisce, il controller viene chiuso internamente.
 */
int controller_fd(
    struct gpiochip_info *info
);

/**
 * @brief Legge le informazioni di una linea GPIO, senza richiederla per l'uso.
 * @param[in] fd Descrittore del controller, ottenuto da controller_fd() o GPIO_CONNECTION().
 * @param[in,out] line Struttura valida: l'helper imposta offset, il kernel scrive le informazioni.
 * @param[in] offset Numero della linea nel controller (per esempio 18 per BCM GPIO18 sul Pi 3 B+).
 * Non e' il numero del pin fisico: GPIO18 corrisponde al pin fisico 12.
 * @return 0 su successo; -1 su errore. Interpretare line solo dopo successo.
 * @note Non legge il livello elettrico e non apre nuovi descrittori.
 */
int controller_lines_info(
    int fd,
    struct gpio_v2_line_info *line,
    int offset
);
/**
 * @brief Richiede al kernel una o piu' linee con la configurazione preparata dal chiamante.
 * @param[in] fd Descrittore del controller GPIO, non request.fd.
 * @param[in,out] request Struttura inizializzata dal chiamante, con config e gli eventuali
 * attributi gia' impostati. L'helper copia offsets/num_lines; su successo il kernel scrive fd.
 * @param[in] offset_line Array di almeno num_lines numeri di linea nel controller.
 * @param[in] num_lines Numero di linee, da 1 a GPIO_V2_LINES_MAX; i limiti dell'array
 * devono essere rispettati dal chiamante: questo helper non li verifica.
 * @return 0 su successo; -1 su errore. request->fd e' un nuovo descrittore valido solo su successo.
 * @note Stampa il descrittore della richiesta su stdout. Usare request->fd per leggere
 * o scrivere i valori e chiuderlo con close_fd() per rilasciare le linee.
 * Il controller resta aperto e deve essere chiuso separatamente dal chiamante.
 */
int controller_lines_request(
	int fd 
	,struct gpio_v2_line_request *request 
	,int offset_line[]
	,int num_lines 
);
/**
 * @brief Legge o imposta i valori delle linee gia' richieste, tramite ioctl.
 * @param[in] fd Descrittore delle linee (request.fd), non quello del controller.
 * @param[in,out] values Struttura valida; l'helper imposta mask e bits prima di ioctl.
 * In lettura il kernel restituisce il risultato in values->bits, da usare solo su successo.
 * @param[in] bits In scrittura: valori logici desiderati (1 attivo, 0 inattivo).
 * In lettura: passare 0; questo valore iniziale viene sostituito dal risultato del kernel.
 * @param[in] mask Bit delle posizioni nell'array della richiesta, NON dei numeri GPIO.
 * Esempio: con offset_line = {18}, la maschera e' 1 (bit 0), non 1 << 18.
 * @param[in] operation GPIO_V2_LINE_GET_VALUES_IOCTL per leggere;
 * GPIO_V2_LINE_SET_VALUES_IOCTL per scrivere linee configurate come uscite.
 * @return 0 su successo; -1 su errore. Il ritorno indica l'esito, non il livello letto.
 * @note Senza ACTIVE_LOW: 1 significa alto, 0 basso. Con ACTIVE_LOW la logica e' invertita.
 * L'helper non apre ne' chiude descrittori e non controlla la validita' degli argomenti.
 */
int controller_lines_action(
	int fd, 
	struct gpio_v2_line_values *values, 
	uint64_t bits, 
	uint64_t mask,
	unsigned long operation
);
/**
 * @brief Apre il controller /dev/gpiochip0 e richiede le linee in un'unica operazione.
 * @param[out] info Struttura valida che riceve le informazioni del controller.
 * @param[in,out] request Richiesta inizializzata dal chiamante con config gia' impostata.
 * Su successo request->fd contiene il descrittore delle linee richieste.
 * @param[in] offset_line Array di almeno num_lines numeri di linea (per esempio {18}).
 * @param[in] num_lines Numero di linee, da 1 a GPIO_V2_LINES_MAX; limiti non verificati dall'helper.
 * @return Descrittore del CONTROLLER (>= 0) su successo; -1 su errore.
 * @note Su successo ci sono DUE descrittori da chiudere: request->fd per le linee
 * e il valore restituito per il controller. Non confonderli: la lettura usa request->fd.
 * Su errore chiude il controller eventualmente aperto e stampa una diagnosi con perror().
 * Non usare request->fd come risultato di questa chiamata se la funzione fallisce.
 */
int GPIO_CONNECTION(
	struct gpiochip_info *info,
	struct gpio_v2_line_request *request,
	int offset_line[], 
	int num_lines
);
/**
 * @brief Esegue una singola close() sul descrittore indicato.
 * @param[in] fd Descrittore valido da chiudere (controller oppure richiesta di linee).
 * @return 0 se close() riesce; -1 se fallisce.
 * @note Non stampa errori, non ritenta e non modifica la variabile del chiamante.
 * Chiudere il descrittore delle linee rilascia la richiesta GPIO.
 */
int close_fd(
	int fd
);

#endif