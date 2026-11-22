"""Concise application events, with opt-in diagnostics and library output."""
from contextlib import contextmanager, redirect_stdout, redirect_stderr
import logging
import os
import warnings

EVENT = 35  # Salient events remain enabled when ordinary warnings are suppressed.
_verbose = False
_model_sink = None
_logger = logging.getLogger('nova.console')
_logger.addHandler(logging.NullHandler())
_logger.propagate = False


class _ConciseErrorFormatter(logging.Formatter):
    def format(self, record):
        # Keep errors actionable without printing full stack traces by default.
        message = f'{record.levelname}: {record.getMessage()}'
        if record.exc_info and record.exc_info[1] is not None:
            error = record.exc_info[1]
            message += f' ({type(error).__name__}: {error})'
        return message


def configure_console(verbose=False):
    """Configure only at application startup, after the macOS bundle re-exec."""
    global _verbose
    _verbose = bool(verbose)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter() if _verbose else _ConciseErrorFormatter())
    logging.basicConfig(level=logging.WARNING if _verbose else logging.ERROR,
                        handlers=[handler], force=True)
    logging.disable(logging.NOTSET if _verbose else logging.WARNING)
    warnings.simplefilter('default' if _verbose else 'ignore')
    if not _verbose:
        os.environ['TQDM_DISABLE'] = '1'
        os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
    output = logging.StreamHandler()
    output.setFormatter(logging.Formatter('%(message)s'))
    _logger.handlers[:] = [output]
    _logger.setLevel(logging.DEBUG)


def diagnostic(*values, sep=' ', end='\n', flush=False):
    """Detailed stage measurements and decisions, available with --verbose."""
    _logger.debug(sep.join(str(value) for value in values))


def event(*values, sep=' ', end='\n', flush=False):
    """A concise lifecycle, API or successful persistence event."""
    _logger.log(EVENT, sep.join(str(value) for value in values))


def api_call(provider, operation):
    event(f'API {provider}: {operation}')


@contextmanager
def model_output():
    """Silence third-party initialization prints, keeping bound log handlers live."""
    global _model_sink
    if _verbose:
        yield
    else:
        # Libraries may retain their import-time stderr in a logging handler.
        # Keep this stream open for the process lifetime instead of leaving them
        # with a closed handle after initialization.
        if _model_sink is None:
            _model_sink = open(os.devnull, 'w')
        with redirect_stdout(_model_sink), redirect_stderr(_model_sink):
            yield
