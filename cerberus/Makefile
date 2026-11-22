control_center: main.o io.o temperature.o gpio.o thermistor.o
	gcc -std=c11 -Wall -Wextra -Wpedantic -pthread main.o io.o temperature.o gpio.o thermistor.o -o control_center -lm
temperature.o: src/temperature.c include/temperature.h
	gcc -std=c11 -Wall -Wextra -Wpedantic -pthread -Iinclude -c src/temperature.c -o temperature.o
io.o: src/io.c include/io.h
	gcc -std=c11 -Wall -Wextra -Wpedantic -pthread -Iinclude -c src/io.c -o io.o
gpio.o: src/gpio.c include/gpio.h
	gcc -std=c11 -Wall -Wextra -Wpedantic -pthread -Iinclude -c src/gpio.c -o gpio.o
thermistor.o: src/thermistor.c include/thermistor.h
	gcc -std=c11 -Wall -Wextra -Wpedantic -pthread -Iinclude -c src/thermistor.c -o thermistor.o
main.o: src/main.c include/io.h include/temperature.h include/gpio.h include/thermistor.h
	gcc -std=c11 -Wall -Wextra -Wpedantic -pthread -Iinclude -c src/main.c -o main.o

# Optional camera capture, called from C through include/camera.h.
# The default control_center target remains unchanged.
CAMERA_CC = gcc
CAMERA_CXX = g++
CAMERA_CPPFLAGS = -Iinclude $(shell pkg-config --cflags libcamera)
CAMERA_LIBS = $(shell pkg-config --libs libcamera)
CAMERA_BUILD = build/camera

.PHONY: camera-check camera-clean
camera-check:
	@pkg-config --exists libcamera || { echo "Install libcamera-dev and pkg-config first."; exit 1; }

$(CAMERA_BUILD):
	mkdir -p $(CAMERA_BUILD)

$(CAMERA_BUILD)/camera.o: src/camera.cpp include/camera.h | camera-check $(CAMERA_BUILD)
	$(CAMERA_CXX) -std=c++20 -Wall -Wextra -Wpedantic -pthread $(CAMERA_CPPFLAGS) -c $< -o $@

$(CAMERA_BUILD)/acquire_frame.o: src/acquire_frame.c include/acquire_frame.h include/camera.h | $(CAMERA_BUILD)
	$(CAMERA_CC) -std=c11 -Wall -Wextra -Wpedantic -Iinclude -c $< -o $@

$(CAMERA_BUILD)/acquire_frame_main.o: src/acquire_frame_main.c include/acquire_frame.h include/camera.h | $(CAMERA_BUILD)
	$(CAMERA_CC) -std=c11 -Wall -Wextra -Wpedantic -Iinclude -c $< -o $@

$(CAMERA_BUILD)/cerberus.o: src/cerberus.c include/gpio.h include/acquire_frame.h include/camera.h include/io.h | $(CAMERA_BUILD)
	$(CAMERA_CC) -std=c11 -Wall -Wextra -Wpedantic -Iinclude -c $< -o $@

$(CAMERA_BUILD)/gpio.o: src/gpio.c include/gpio.h | $(CAMERA_BUILD)
	$(CAMERA_CC) -std=c11 -Wall -Wextra -Wpedantic -Iinclude -c $< -o $@

$(CAMERA_BUILD)/io.o: src/io.c include/io.h | $(CAMERA_BUILD)
	$(CAMERA_CC) -std=c11 -Wall -Wextra -Wpedantic -Iinclude -c $< -o $@

acquire_frame: $(CAMERA_BUILD)/acquire_frame_main.o $(CAMERA_BUILD)/acquire_frame.o $(CAMERA_BUILD)/camera.o
	$(CAMERA_CXX) -pthread $^ $(CAMERA_LIBS) -o $@

# Build and run from cerberus/: make cerberus; ./cerberus [output.ppm]
cerberus: $(CAMERA_BUILD)/cerberus.o $(CAMERA_BUILD)/io.o $(CAMERA_BUILD)/gpio.o $(CAMERA_BUILD)/acquire_frame.o $(CAMERA_BUILD)/camera.o
	$(CAMERA_CXX) -pthread $^ $(CAMERA_LIBS) -o $@

camera-clean:
	rm -f $(CAMERA_BUILD)/camera.o $(CAMERA_BUILD)/acquire_frame.o $(CAMERA_BUILD)/acquire_frame_main.o $(CAMERA_BUILD)/cerberus.o $(CAMERA_BUILD)/gpio.o $(CAMERA_BUILD)/io.o acquire_frame cerberus
