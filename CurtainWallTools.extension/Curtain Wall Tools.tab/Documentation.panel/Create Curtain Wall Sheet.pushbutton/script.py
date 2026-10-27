# -*- coding: utf-8 -*-
"""Loader for the Curtain Wall Sheets pyRevit command."""
from __future__ import print_function

import os

_PARTS = [
    "01_command.py",
    "02_command.py",
    "03_command.py",
    "04_command.py",
    "05_command.py",
    "06_command.py",
    "07_command.py",
    "08_command.py",
]

_BASE = os.path.dirname(__file__)
for _part in _PARTS:
    _path = os.path.join(_BASE, "command_parts", _part)
    try:
        execfile(_path, globals(), globals())
    except NameError:
        with open(_path, "rb") as _stream:
            _source = _stream.read()
        exec(compile(_source, _path, "exec"), globals(), globals())
