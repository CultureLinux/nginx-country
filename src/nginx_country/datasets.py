"""Lecture vérifiée des collectes complètes retenues."""
import hashlib
import json
from pathlib import Path
import re

from .countries import ISO_COUNTRIES
from .fetch import validate_ipverse, validate_zone


def load_dataset(root, source):
    if source not in ('ipverse', 'ipdeny'):
        raise ValueError('source inconnue')
    base = (Path(root) / source / 'all').resolve(strict=True)
    meta = json.loads((base / 'metadata.json').read_text(encoding='utf-8'))
    if (meta.get('source') != source or meta.get('scope') != 'all-listed-unverified-completeness'
            or meta.get('errors') != [] or not isinstance(meta.get('historical_reference'), bool)
            or not isinstance(meta.get('files'), list) or not meta['files']):
        raise ValueError('manifeste ancien ou invalide : relancer la collecte')
    if source == 'ipverse' and not re.fullmatch(r'[0-9a-f]{40}', meta.get('revision') or ''):
        raise ValueError('révision IPverse manquante : relancer la collecte')
    countries, special, seen = {}, set(), set()
    for entry in meta['files']:
        name, code = entry['file'], entry['country']
        if not isinstance(name, str) or name in seen or not re.fullmatch(r'[A-Z]{2}', code):
            raise ValueError('entrée de manifeste invalide ou dupliquée')
        seen.add(name)
        expected = f'{code.lower()}.json' if source == 'ipverse' else None
        match = re.fullmatch(r'ipv([46])/([a-z]{2})-aggregated\.zone', name) if source == 'ipdeny' else None
        if (source == 'ipverse' and name != expected) or (source == 'ipdeny' and (not match or match.group(2) != code.lower())):
            raise ValueError('chemin de manifeste incorrect')
        path = (base / name).resolve(strict=True)
        if base not in path.parents:
            raise ValueError('chemin hors du jeu')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry.get('sha256') or len(data) != entry.get('bytes'):
            raise ValueError('empreinte ou taille incorrecte : ' + name)
        category = 'country' if code in ISO_COUNTRIES else 'special'
        if entry.get('category') != category:
            raise ValueError('classification incorrecte : ' + name)
        status = entry.get('status')
        if status == 'special-empty-confirmed' and source == 'ipdeny' and name == 'ipv4/ap-aggregated.zone' and not data:
            special.add(code)
            continue
        if status != 'valid':
            raise ValueError('fichier non validé : ' + name)
        if source == 'ipverse':
            validate_ipverse(data, code)
            prefixes = json.loads(data)['prefixes']
            families = {key: {'status': 'present' if values else 'empty', 'prefixes': values} for key, values in prefixes.items() if key in ('ipv4', 'ipv6')}
        else:
            family = 'ipv' + match.group(1)
            validate_zone(data, int(match.group(1)))
            families = {family: {'status': 'present', 'prefixes': [line.strip() for line in data.decode().splitlines() if line.strip() and not line.lstrip().startswith('#')]}}
        if category == 'special':
            special.add(code)
            continue
        country = countries.setdefault(code, {key: {'status': 'absent', 'prefixes': []} for key in ('ipv4', 'ipv6')})
        country.update(families)
    if not countries:
        raise ValueError('aucun pays dans la collecte')
    return {'source': source, 'revision': meta.get('revision'), 'countries': countries, 'special_codes': sorted(special), 'input_files': meta['files'], 'historical_reference': meta['historical_reference']}
