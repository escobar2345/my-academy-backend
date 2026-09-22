"""Unified import adapter for the BOI RSU module.

The original project stores the app in a directory named ``boi-rsu`` with a
hyphen, which is not a valid Python package name. This adapter gives the rest of
backend a normal module import path while loading the actual implementation file
with a BOM-safe encoding.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent / 'boi-rsu' / 'boirsu.py'


def load_module():
    """Load the BOI RSU implementation as a standard module object."""
    if not _MODULE_PATH.exists():
        raise FileNotFoundError(f'BOI RSU script not found at {_MODULE_PATH}')

    module_name = 'mirofish_boi_rsu'
    spec = importlib.util.spec_from_file_location(module_name, _MODULE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f'Unable to load BOI RSU module from {_MODULE_PATH}')

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    source = _MODULE_PATH.read_text(encoding='utf-8-sig')
    code = compile(source, str(_MODULE_PATH), 'exec')
    exec(code, module.__dict__)
    return module


def __getattr__(name):
    module = load_module()
    return getattr(module, name)
