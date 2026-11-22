"""Bounded text-only producer; all MLX inference stays on Nova's one worker."""
import queue
import re
import threading
from time import perf_counter


class SentenceBuffer:
    # Wait for following whitespace: a dot at a delta boundary may be decimal.
    _boundary = re.compile(r'[.!?]+["”’\')\]]*\s+|\n+')
    _abbreviations = {'sig', 'sig.ra', 'sig.na', 'dott', 'dr', 'mr', 'mrs', 'ms',
                      'prof', 'ing', 'avv', 'ecc', 'es', 'etc', 'e.g', 'i.e', 'p.es'}

    def __init__(self, minimum_chars=0):
        self.pending = ''
        self.minimum_chars = minimum_chars

    def push(self, delta):
        self.pending += delta
        if len(self.pending) > 16384:
            raise RuntimeError('Frase GPT troppo lunga.')
        result, start = [], 0
        for match in self._boundary.finditer(self.pending):
            candidate = self.pending[start:match.end()]
            stripped = candidate.rstrip()
            if stripped.endswith('.'):
                word = stripped.split()[-1].rstrip('.').casefold()
                if word in self._abbreviations or (len(word) == 1 and word.isalpha()):
                    continue
            if candidate.strip():
                if len(candidate.strip()) < self.minimum_chars:
                    continue
                result.append(candidate)
            start = match.end()
        self.pending = self.pending[start:]
        return result

    def finish(self):
        tail, self.pending = self.pending, ''
        return [tail] if tail.strip() else []


class SentenceStream:
    """Read HTTP concurrently with speech; accept only a completed final reply.

    Closing joins the reader before the next turn can use the backend. A blocked
    network read may still take its existing socket timeout to finish after Stop.
    """
    def __init__(self, request, check_open, minimum_chars=0):
        self.request, self.check_open = request, check_open
        self.queue = queue.Queue(maxsize=8)
        self.done = threading.Event()
        self.abort = threading.Event()
        self.result = None
        self.error = None
        self.request_seconds = None
        self.minimum_chars = minimum_chars

    def _check(self):
        self.check_open()
        if self.abort.is_set():
            raise RuntimeError('Lettura GPT annullata.')

    def _put(self, sentence):
        while True:
            self._check()
            try:
                self.queue.put(sentence, timeout=.05)
                return
            except queue.Full:
                continue

    def _run(self):
        sentences = SentenceBuffer(self.minimum_chars)
        def delta(text):
            self._check()
            for sentence in sentences.push(text):
                self._put(sentence)
        try:
            start = perf_counter()
            result = self.request(delta, self._check)
            self.request_seconds = perf_counter() - start
            self._check()
            for sentence in sentences.finish():
                self._put(sentence)
            self.result = result
        except Exception as exc:
            self.error = exc
        finally:
            self.done.set()

    def __enter__(self):
        self.thread = threading.Thread(target=self._run, name='nova-gpt-reader', daemon=True)
        self.thread.start()
        return self

    def __iter__(self):
        while True:
            self._check()
            if self.error is not None:
                raise self.error
            if self.done.is_set() and self.queue.empty():
                return
            try:
                yield self.queue.get(timeout=.05)
            except queue.Empty:
                if self.done.is_set():
                    if self.error is not None:
                        raise self.error
                    return

    def __exit__(self, *exc):
        self.abort.set()
        self.thread.join()
