# Camera capture from C

The tutor maintains the private camera backend. C programs use only
`include/camera.h`; no libcamera or C++ types appear in the public interface.

## Build and run on the Raspberry Pi

Requirements: Linux, a supported connected camera, a C compiler, a C++20
compiler, `pkg-config` and `libcamera-dev` matching the installed camera stack.
The target is the student's Pi 3B+ with Camera Module 3 NoIR and libcamera 0.8.0.

From the `cerberus` directory:

```sh
make acquire_frame
./acquire_frame
```

The student's `src/acquire_frame.c` allocates a 640x480 RGB destination, captures
one image, writes `camera-frame.ppm` in the execution directory and frees the
destination. An existing file with that name is overwritten after capture
success. The current caller requests a 1000 ms frame-wait timeout.

The main Makefile compiles the caller as C11, the private backend as C++20, and
links them with libcamera. The default `control_center` target is unchanged.
`make camera-clean` removes the camera executable and its two object files.

## C contract

- `cerberus_camera_rgb_size(width, height, &capacity)` checks the dimensions and
  calculates `width * height * 3`, rejecting overflow.
- Allocate the destination in C, check `malloc`, then call
  `cerberus_camera_capture_rgb(width, height, pixels, capacity, timeout_ms,
  error, error_size)`.
- Return value: zero on success, a negative errno-style code on failure.
  The optional error buffer receives a NUL-terminated diagnostic.
- Success produces top-to-bottom rows of RGB8, R then G then B per pixel,
  with no row padding or header. The caller owns and frees the destination,
  and the data remains valid after the camera has been closed.
- Failure leaves the destination unchanged; its content must not be treated
  as a newly acquired frame. See the header for full argument requirements.

## Backend behavior and limits

The backend selects the first enumerated camera (and fails if it cannot acquire
it). It configures XRGB8888, verifies dimensions/format, allocates compatible
buffers, and queues requests. After discarding eight successful frames, it
selects an image, stops capture and converts B,G,R,X memory bytes to packed RGB,
respecting row stride and DMA-BUF synchronization. All camera resources are
released before return. Discarded frames reuse the pool; they are not an image
history. Settling time does not guarantee exposure, white-balance or autofocus
lock. Default libcamera processing is used.

Each synchronous call reopens and configures the camera. Continuous video,
pre-event history and AI inference are not implemented. The timeout, from
1 to 60000 ms, bounds frame waiting, not native initialization/start/stop calls,
conversion, cleanup or waiting for another call. It cannot interrupt a hung
driver. Calls through the module are serialized; do not independently run
another CameraManager concurrently in the same process.

## Files and validation

```text
include/camera.h         public C interface
src/camera.cpp           private camera backend and pixel conversion
src/acquire_frame.c      student's C application
Makefile                 default sensor build plus optional acquire_frame target
```

Local checks cover RGB channel order, row padding, truncation, bounds and
overflow, including sanitizer checks. The C caller passes a C11 syntax check;
the backend compiles against official libcamera headers on the development Mac.
These do not validate Linux linking, DMA operation or capture on the Pi.
The previous tutor demo and conversion test were archived outside the repository
during cleanup; the student's exercises remain in `tests/`.

Actual compilation, image capture and quality, repeated hardware calls and
busy/disconnected-camera behavior still require on-device verification.
