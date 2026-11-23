"""Lecture d'un fichier .env (KEY=VALUE) sans dépendance externe."""
import os
from pathlib import Path
import re

_LINE = re.compile(r'^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$')


def read_env_file(path):
    path = Path(path)
    if not path.is_file():
        return {}
    values = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = _LINE.match(line)
        if not match:
            continue
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
            value = value[1:-1]
        values[match.group(1)] = value
    return values


def load_env(path='.env'):
    """Charge le fichier dans os.environ ; une variable déjà définie reste prioritaire."""
    for key, value in read_env_file(path).items():
        os.environ.setdefault(key, value)
