#ifndef CERBERUS_CAMERA_H
#define CERBERUS_CAMERA_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* All functions return 0 on success or a negative errno-style code on error. */

/* Calculate the required capacity for tightly packed RGB8: width * height * 3.
 * On error, *size is unchanged. Zero dimensions and overflow are rejected. */
int cerberus_camera_rgb_size(unsigned int width, unsigned int height,
                             size_t *size);

/* Capture ONE image from the first camera reported by libcamera.
 *
 * pixels is owned by the C caller and must have at least the capacity returned
 * by cerberus_camera_rgb_size(). On success the image is exactly width x height,
 * row-major, three bytes per pixel in R,G,B order, with no row padding/header.
 * Extra capacity is untouched. On failure the entire destination is unchanged.
 *
 * This synchronous call opens/configures the camera, discards eight successful
 * startup frames, captures a frame, and releases its resources before returning.
 * Discarding frames allows settling time but does NOT guarantee AE/AWB/AF lock.
 * timeout_ms (1..60000) bounds the wait for frames after capture starts; camera
 * initialization, native calls, cleanup and waiting for another call are outside
 * that timeout. Calls through this module are serialized. Do not operate another
 * libcamera CameraManager in the same process at the same time.
 *
 * error is an optional caller-owned message buffer; pass NULL and 0 to omit it.
 * If error_size > 0, error must be non-NULL and is always NUL-terminated.
 * error must not overlap pixels. No C++ object or exception crosses this API.
 * Requires Linux, libcamera development files and a free supported camera.
 */
int cerberus_camera_capture_rgb(unsigned int width, unsigned int height,
                                uint8_t *pixels, size_t capacity,
                                unsigned int timeout_ms,
                                char *error, size_t error_size);

#ifdef __cplusplus
}
#endif

#endif
