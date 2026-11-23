#define _POSIX_C_SOURCE 200809L

#include <stdio.h>       // printf, fprintf, perror
#include <poll.h>        // poll, struct pollfd, POLLIN...
#include <unistd.h>      // read, ssize_t
#include <errno.h>       // errno, EINTR
#include <string.h>      // strerror
#include <stdlib.h>
#include <stdint.h>
#include <io.h>
#include <linux/gpio.h>  // strutture e costanti GPIO
#include "gpio.h" // helper del progetto
#include "camera.h"
#include "acquire_frame.h"
#include <spawn.h>
#include <sys/wait.h>


extern char **environ;
static int run_face_detection(char *path, char *args[]){
    // Process ID for face_detection.py
    pid_t child_pid;

    int spawn_error = posix_spawn(
        &child_pid,
        path,
        NULL,
        NULL,
        args,
        environ
    );
    if (spawn_error != 0){
        fprintf(stderr,"Error while opening face_detection.py: %s", strerror(spawn_error));
        return 1;
    }
    int child_status;
    // Require a blocking waiting of the child process
    /* Wait for Python. If a signal interrupts this waiting, repeat */
    pid_t waited;
    do {
        waited = waitpid(child_pid, &child_status, 0);
    } while (waited == -1 && errno == EINTR);
    /* Cannot retriev Python result. */
    if (waited == -1) {
        perror("Cannot wait for Python\n");
        return 1;
    }
    /* Checking Python return code. */
    if (WIFEXITED(child_status)) {
        int python_exit_code = WEXITSTATUS(child_status);

        if (python_exit_code == 0) {
            printf("Python completed successfully\n");
            return 0;
        }
        fprintf(stderr,"Python failed with exit code %d\n", python_exit_code);
        return 1;
    }
    /* Checking if Python was terminated by a signal. */
    if (WIFSIGNALED(child_status)) {
        fprintf(stderr, "Python terminated by signal %d\n", WTERMSIG(child_status));
        return 1;
    } else {
        fprintf(stderr, "Generic error\n");
        return 1;
    }
}

int main(int argc, char *argv[]){
    // Set the default before libcamera initializes; preserve an explicit override.
    if (setenv("LIBCAMERA_LOG_LEVELS", "*:ERROR", 0) == -1) {
        perror("Cannot configure libcamera loggin\n");
        return EXIT_FAILURE;
    }

    struct gpiochip_info info = {0};          
    struct gpio_v2_line_request request = {0};
    struct gpio_v2_line_event event = {0};
    struct pollfd fds[1] = {0};
    int lines[] = {18};
    int ready, rc;
    char *path = (argc == 2) ? argv[1] : "images/captured/camera-frame.ppm";
    ssize_t n;
    int exit_value = 0;
    int num_lines = 1;
    int fd_controller;
    // Building string to call face_detection.py
    char *python_path = "/home/pi/projects/synapse/cerberus/.venv/bin/python";
    char *python_args[] = {
        python_path,
        "src/face_detection.py",
        path,
        "images/face_detection",
        NULL
    };
    

    

    print_cerberus_logo();

    //Initializing the request configuration flags for the movement sensor
    request.config.flags = GPIO_V2_LINE_FLAG_INPUT |
    GPIO_V2_LINE_FLAG_BIAS_DISABLED |
    GPIO_V2_LINE_FLAG_EDGE_RISING |
    GPIO_V2_LINE_FLAG_EDGE_FALLING;


    //Opening of the GPIO
    fd_controller = GPIO_CONNECTION(&info, &request,lines,num_lines);
    if(fd_controller == -1){
        perror("Failed to open GPIO");
        return 1;
	}

    fds[0].fd = request.fd;
    fds[0].events = POLLIN;

    printf("System armed!\n");
    while(1){
        fds[0].revents = 0;

        
        ready = poll(fds, 1, -1);
        if (ready == -1 && errno == EINTR){
            continue;
        }
        if (ready == -1){
            fprintf(stderr, "Waiting for monitored events with poll failed: %s\n", strerror(errno));
            exit_value = 30;
            goto closing;
        }

        if(fds[0].revents & POLLERR){
            fprintf(stderr, "GPIO descriptor reported POLLERR\n");
            exit_value = 33;
            goto closing;  
        }else if(fds[0].revents & POLLNVAL){
            fprintf(stderr, "GPIO descriptor reported POLLNVAL\n");
            exit_value = 34;
            goto closing;
        }else if(fds[0].revents & POLLIN){
            do {
                n = read(request.fd, &event, sizeof(event));
            } while (n == -1 && errno == EINTR);
            if(n == -1){
                fprintf(stderr, "Reading GPIO event failed: %s\n", strerror(errno));
                exit_value = 35;
                goto closing;
            }
            if(n == (ssize_t)sizeof(event)){
                if (event.id == GPIO_V2_LINE_EVENT_RISING_EDGE) {
                    //printf("Sensore: passaggio da BASSO ad ALTO\n");
                    rc = acquire_and_save_frame(path);
                    if(rc != 0){
                        exit_value = 99;
                        goto closing;
                    }
                    // Call face_detection.py
                    rc = run_face_detection(python_path, python_args);
                    if (rc == 0){
                        printf("Face detection completed\n");
                    } else {
                        fprintf(stderr, "Face detection failed.\n");
                        exit_value = 91;
                        goto closing;
                    }
                } else if (event.id == GPIO_V2_LINE_EVENT_FALLING_EDGE) {
                    //printf("Sensore: passaggio da ALTO a BASSO\n");
                }
            }
            else { //Incomplete GPIO event read
                fprintf(stderr, "[E036] GPIO event: received %zd bytes, expected %zu\n", n, sizeof event);
                exit_value = 36;
                goto closing;
            }
        }else if(fds[0].revents & POLLHUP){
            fprintf(stderr, "GPIO descriptor reported POLLHUP\n");
            exit_value = 37;
            goto closing;
        }
    }


    closing:
        if (request.fd != -1){
            if (close_fd(request.fd) == -1){
                fprintf(stderr, "Closing GPIO line descriptor failed: %s\n", strerror(errno));
                if (exit_value == 0) exit_value = 92;
            }
            request.fd = -1;
        }
        if (fd_controller != -1){
            if (close_fd(fd_controller) == -1){
                fprintf(stderr, "Closing GPIO controller descriptor failed: %s\n", strerror(errno));
                if (exit_value == 0) exit_value = 93;
            }
            fd_controller = -1;
        }
        return exit_value;

}