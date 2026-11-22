# Cerberus

Cerberus is the Raspberry Pi acquisition module in [Project Synapse](../README.md). It captures a camera frame when a PIR sensor reports motion. A standalone Python script detects faces in still images and saves individual crops for later recognition work.

## Hardware and runtime

- Raspberry Pi 3 B+ running Linux with GPIO character-device API v2.
- Raspberry Pi Camera Module 3 NoIR, accessed through libcamera.
- HC-SR501 PIR sensor, currently configured with its jumper in L mode.
- C application logic with a C++20 libcamera backend exposed through `include/camera.h`.

The current Raspberry Pi installation is console-only. The face-detection script uses headless OpenCV and saves its output to disk.

The configured sensor connections are:

| HC-SR501 | Raspberry Pi connection |
|---|---|
| VCC | 5 V, physical pin 2 |
| GND | Ground, physical pin 6 |
| OUT | BCM GPIO18, physical pin 12 |

BCM numbering and physical header positions are different numbering schemes. These connections describe the HC-SR501 used in this build; verify the pin labels on the actual module before wiring. The earlier thermistor/button/LED circuit is documented separately in [Control Center](../docs/control-center.md).

## Build

The camera targets require GCC, a C++20-capable G++, Make, `pkg-config`, libcamera development headers and a working libcamera camera stack. The application also needs permission to access the camera and `/dev/gpiochip0`.

From `cerberus/`:

```sh
make camera-check
make cerberus
mkdir -p images
```

Plain `make` builds the earlier `control_center` target. Select `cerberus` explicitly for motion-triggered capture.

## Motion-triggered capture

```sh
./cerberus
```

The application requests both edges on BCM GPIO18 and waits using `poll`. A rising edge calls `acquire_and_save_frame`; a falling edge is logged without taking another image.

The default output is `images/camera-frame.ppm`, a 640×480 RGB P6 PPM. Each capture overwrites the previous file. Supply a single output-path argument to choose another destination:

```sh
./cerberus images/motion.ppm
```

Relative paths are resolved from the working directory, and the destination directory must exist. Capture or save failures terminate the acquisition loop with a nonzero exit status. Stop the program with Ctrl+C.

Capture and saving are synchronous. The GPIO loop waits for them to finish before reading another event. Latency, event backlog behavior and sustained operation have not yet been benchmarked. An already-high sensor output does not generate a retroactive rising edge when the program starts.

The application defaults libcamera logging to errors unless `LIBCAMERA_LOG_LEVELS` is already set. For camera diagnostics:

```sh
LIBCAMERA_LOG_LEVELS='*:INFO' ./cerberus
```

## Manual capture

The standalone executable takes one frame without waiting for the PIR:

```sh
make acquire_frame
./acquire_frame images/manual.ppm
```

Without a path argument, it writes `camera-frame.ppm` in the working directory. The camera API returns RGB bytes; the capture helpers write the PPM file. The default frame contains 921,600 pixel-data bytes plus the PPM header.

## Face detection

The script is [src/face_detection.py](src/face_detection.py), using OpenCV's `FaceDetectorYN` and `models/face_detection_yunet_2023mar.onnx`. Input and generated images are excluded from Git; provide an image to analyze.

Its current workflow is:

1. Load the image supplied as the first command-line argument.
2. Configure YuNet with the image width and height and a score threshold of 0.6.
3. Detect faces and bound crop coordinates to the image dimensions.
4. Copy each valid crop from the unannotated image.
5. Draw rectangles on a separate image and save JPEG outputs.

Output files are `face_1.jpg`, `face_2.jpg`, and so on, plus `yunet_result.jpg` for the annotated image, all inside the directory supplied as the second argument. A new run reuses these names; files left by a run with more faces are not removed automatically. No output is written when no faces are detected.

The script uses `opencv-python-headless` on the Pi; the installed version in the current setup is 4.14.0. No TensorFlow or Keras runtime is needed for this detector. From `cerberus/`, activate the Python environment and pass an input image and output directory:

```sh
python src/face_detection.py images/test_multiple_faces.jpeg images
```

Single-face and five-person photos have been checked on Mac. Detection, annotated-image saving and individual crop saving have also been run on the Raspberry Pi, with output transferred to the Mac for inspection. A large portrait initially produced partial detections; reducing the image to 25% resolved that case. Resizing is currently a manual experiment, not an automatic scale-selection pipeline.

Both arguments are required; relative paths use the working directory. The output directory must already exist, while the model is located relative to the script. An unreadable input or failed save returns a nonzero exit status; a completed analysis with no faces returns zero.

YuNet detects face locations, not identities. Detection on a photo taken by the Cerberus camera is the next test; the Python script is not yet invoked by the C motion-capture application.

## Next steps

- Test detection on an image captured by the Camera Module 3 NoIR.
- Define how the C acquisition application passes completed images to face detection.
- Collect a face dataset across separate sessions and train a Keras recognizer with known/unknown evaluation.
- Add bounded frame history, event clips and Atlas event delivery.

The current implementation captures still images. Continuous recording, pre/post-event clips, identity recognition and remote services are not implemented.
