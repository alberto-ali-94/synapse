"""Resolve shared local assets independently of the working directory."""
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def model_source(repository):
    """Use a complete cached snapshot without Hub metadata network requests."""
    from huggingface_hub import try_to_load_from_cache
    cached = try_to_load_from_cache(repository, 'config.json')
    return str(Path(cached).parent) if isinstance(cached, str) else repository
