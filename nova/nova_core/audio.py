"""Continuous, cancellable TTS playback. Imports open no audio devices."""
from collections import deque
import threading
import math
from time import monotonic


class StreamingSpeech:
    """Single output stream, bounded queue, ramps only at utterance edges."""
    def __init__(self, sd, app, device, startup_seconds=.6, max_buffer_seconds=8):
        import numpy as np
        self.np, self.sd, self.app, self.device = np, sd, app, device
        self.startup_seconds, self.max_buffer_seconds = startup_seconds, max_buffer_seconds
        self.rate = None
        self.stream = None
        self.queue = deque()
        self.offset = 0
        self.buffered = 0
        self.lock = threading.Lock()
        self.changed = threading.Event()
        self.done = threading.Event()
        self.drain_requested = threading.Event()
        self.finished = False
        self.completed = False
        self.tail = np.empty(0, dtype=np.float32)
        self.started = False
        self.underruns = 0
        self._pending_underruns = 0
        self.device_underflows = 0
        self.callback_error = None
        self.output_latency = .2
        self.output_end_deadline = None
        self.source_paused = False
        self.segment_first = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.stream is not None:
            self.app._release_output(self.stream, drain=exc[0] is None and self.completed)

    def _enqueue(self, data, final=False, resume=True):
        # Producer waits with cancellation checks instead of growing without bound.
        while True:
            self.app._check_open()
            if self.done.is_set():
                raise RuntimeError('Speech output stopped while generating')
            with self.lock:
                if self.buffered < self.max_buffer_seconds * self.rate:
                    self.queue.append(data)
                    self.buffered += len(data)
                    if resume:
                        self.underruns += self._pending_underruns
                        self._pending_underruns = 0
                        self.source_paused = False
                    if final:
                        self.finished = True
                    break
            if self.done.is_set():
                raise RuntimeError('Speech output stopped while generating')
            self.changed.wait(.05)
            self.changed.clear()
        if not self.started and self.buffered >= round(self.startup_seconds * self.rate):
            self._start()

    def push(self, audio, rate):
        self.app._check_open()
        if rate <= 0 or int(rate) != rate:
            raise ValueError('Invalid speech sample rate')
        if self.rate is not None and self.rate != rate:
            raise ValueError('Speech sample rate changed between chunks')
        data = self.np.array(audio, dtype=self.np.float32, copy=True)
        if data.ndim != 1 or not self.np.isfinite(data).all():
            raise ValueError('Invalid speech audio')
        if not len(data):
            return
        first = self.rate is None or self.segment_first
        self.segment_first = False
        self.rate = int(rate)
        ramp = max(1, round(.005 * self.rate))
        # Fixed gain across chunks avoids level changes at chunk boundaries.
        data *= .98
        self.np.clip(data, -.98, .98, out=data)
        if first:
            n = min(ramp, len(data))
            data[:n] *= self.np.linspace(0, 1, n, dtype=self.np.float32)
            data = self.np.concatenate((self.np.zeros(round(.02*self.rate), dtype=self.np.float32), data))
        data = self.np.concatenate((self.tail, data))
        # Keep the last 5 ms until we know whether another chunk follows.
        keep = min(ramp, len(data))
        self.tail = data[-keep:].copy()
        if len(data) > keep:
            # Split unusually large runtime chunks to maintain the queue bound.
            ready = data[:-keep]
            size = max(1, round(.25*self.rate))
            for start in range(0, len(ready), size):
                self._enqueue(ready[start:start+size].copy())

    def _callback(self, outdata, frames, timing, status):
        outdata.fill(0)
        if self.app._cancel.is_set() or self.app._closed:
            raise self.sd.CallbackAbort
        stop = False
        try:
            with self.lock:
                if status and status.output_underflow:
                    self.device_underflows += 1
                written = 0
                while written < frames and self.queue:
                    current = self.queue[0]
                    count = min(frames-written, len(current)-self.offset)
                    outdata[written:written+count, 0] = current[self.offset:self.offset+count]
                    self.offset += count
                    self.buffered -= count
                    written += count
                    if self.offset == len(current):
                        self.queue.popleft()
                        self.offset = 0
                if written < frames and not self.finished and not self.source_paused:
                    # Confirm starvation only if more audio follows in this
                    # sentence. Its generator may simply be returning now.
                    self._pending_underruns += 1
                if self.finished and not self.queue:
                    now = monotonic()
                    if self.output_end_deadline is None:
                        # Callback consumption is earlier than physical playback.
                        # Keep the device running with silence until this final
                        # block's estimated DAC time, plus a small safety margin.
                        pending = self.output_latency
                        dac = getattr(timing, "outputBufferDacTime", None)
                        current = getattr(timing, "currentTime", None)
                        if isinstance(dac, (int, float)) and isinstance(current, (int, float)):
                            delta = dac - current
                            if math.isfinite(delta) and delta >= 0:
                                pending = max(pending, delta)
                        self.output_end_deadline = now + pending + written / self.rate + .05
                    else:
                        stop = now >= self.output_end_deadline
        except Exception as exc:
            self.callback_error = exc
            raise self.sd.CallbackAbort
        finally:
            self.changed.set()
        if stop:
            # Speech has passed its scheduled output time; only silence remains.
            self.drain_requested.set()
            raise self.sd.CallbackStop

    def _start(self):
        self.app._check_open()
        self.stream = self.sd.OutputStream(
            samplerate=self.rate, channels=1, dtype='float32', device=self.device,
            latency=.2, blocksize=0, callback=self._callback,
            finished_callback=self.done.set,
        )
        latency = getattr(self.stream, "latency", None)
        if isinstance(latency, (int, float)) and math.isfinite(latency) and latency >= 0:
            self.output_latency = max(.2, float(latency))
        self.app._start_output(self.stream)
        self.started = True
        self.app._publish('speak', self.app.config.text('Nova sta parlando.', 'Nova is speaking.'))

    def finish(self):
        self.app._check_open()
        self._check_callback_error()
        if self.rate is None:
            return
        with self.lock:
            self._pending_underruns = 0
        if len(self.tail):
            self.tail *= self.np.linspace(1, 0, len(self.tail), dtype=self.np.float32)
            self._enqueue(self.tail)
            self.tail = self.np.empty(0, dtype=self.np.float32)
        self._enqueue(self.np.zeros(round(.02*self.rate), dtype=self.np.float32), final=True)
        if not self.started:
            self._start()
        while not self.done.wait(.05):
            self.app._check_open()
            self._check_callback_error()
            if not self.stream.active:
                # PortAudio may report inactive before finished_callback runs.
                # Accept only an explicitly requested normal final drain.
                if self.drain_requested.is_set():
                    break
                raise RuntimeError('Speech output stopped unexpectedly')
        self.app._check_open()
        self._check_callback_error()
        if not self.drain_requested.is_set():
            raise RuntimeError('Speech output stopped unexpectedly')
        self.completed = True

    def end_segment(self):
        """A sentence ended: fade its tail while waiting for the next text.

        Silence between complete sentences is intentional, not starvation of an
        unfinished sentence. Keep one device stream and ramp the next onset.
        """
        self.app._check_open()
        with self.lock:
            self.source_paused = True
            self._pending_underruns = 0
        if len(self.tail):
            self.tail *= self.np.linspace(1, 0, len(self.tail), dtype=self.np.float32)
            self._enqueue(self.tail, resume=False)
            self.tail = self.np.empty(0, dtype=self.np.float32)
        self.segment_first = True
        if self.rate is not None and not self.started:
            self._start()

    def _check_callback_error(self):
        if self.callback_error is not None:
            raise RuntimeError('Speech output callback failed') from self.callback_error
