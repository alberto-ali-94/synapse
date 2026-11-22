#include "camera.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

static int save_ppm(const char *path, const unsigned char *pixels,
                    unsigned int width, unsigned int height, size_t bytes)
{
    FILE *file = fopen(path, "wb");
    if (!file)
        return -1;
    int result = 0;
    if (fprintf(file, "P6\n%u %u\n255\n", width, height) < 0 ||
        fwrite(pixels, 1, bytes, file) != bytes)
        result = -1;
    if (fclose(file) != 0)
        result = -1;
    return result;
}


int main(int argc, char *argv[]){
    const unsigned int width = 640;
    const unsigned int height = 480;

    size_t capacity = 0;
    uint8_t *buffer = NULL;
    char error[256];
    int rc, exit_code;
    exit_code = EXIT_SUCCESS;
    char *path;
    if (argc == 2){
        path = argv[1];
    }else{
        path = "camera-frame.ppm";
    }

    rc = cerberus_camera_rgb_size(width, height, &capacity);
    if (rc != 0){
        fprintf(stderr,"Error allocating the capacity needed\n");
        exit_code = EXIT_FAILURE;
        goto closing;
    }
    printf("Byte needed to store the image: %zu\n",capacity);

    buffer = malloc(capacity);
    if(buffer == NULL){
        fprintf(stderr, "Cannot allocate RGB destination\n");
        exit_code = EXIT_FAILURE;
        goto closing;
    }

    rc = cerberus_camera_capture_rgb(width,height, buffer, capacity, 1000, error, sizeof(error));
    if (rc != 0){
        fprintf(stderr,"Capture failed (%d): %s\n",rc, error);
        exit_code = EXIT_FAILURE;
        goto closing;
    }
    rc = save_ppm(path,buffer, width,height,capacity);
    if (rc != 0){
        fprintf(stderr,"Saving failed (%d)\n", rc);
        exit_code = EXIT_FAILURE;
        goto closing;
    }

    printf("Captured %u x %u RGB image (%zu bytes): %s\n",
           width, height, capacity, path);


    closing:
        
        if(buffer != NULL){
            free(buffer);
        }
        return exit_code;
}




