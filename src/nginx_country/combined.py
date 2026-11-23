"""Jeu Nginx combiné : union pour allow, intersection pour deny."""
import datetime
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from .compare import _load, _read_country, _intervals, _intersection
from .countries import ISO_COUNTRIES
from .geolite import load_geolite
from .normalize import normalize_cidrs


SOURCES = ('ipverse', 'ipdeny', 'geolite')


def combine_family(inputs, family):
    """Règles d'une famille IP à partir des trois sources.

    allow : union des sources disponibles, pour ne jamais bloquer une famille
    qu'une source ne publie pas. deny : intersection, uniquement si les trois
    sources sont disponibles ; sinon aucun deny n'est émis.
    """
    key = 'ipv' + str(family)
    available = [s for s in SOURCES if inputs[s]['status'] != 'absent']
    if not available:
        return {'status': 'absent', 'allow': [], 'deny': []}
    allow = normalize_cidrs([p for s in available for p in inputs[s]['prefixes']], family)
    deny = []
    if len(available) == len(SOURCES):
        a, b, c = (_intervals(inputs[s]['prefixes'], family) for s in SOURCES)
        addr = ipaddress.IPv4Address if family == 4 else ipaddress.IPv6Address
        deny = [str(net) for start, end in _intersection(_intersection(a, b), c)
                for net in ipaddress.summarize_address_range(addr(start), addr(end))]
    return {'status': 'complete' if len(available) == len(SOURCES) else 'partial', 'allow': allow, 'deny': deny}


def build_combined(input_root, archive, output):
    output = Path(output)
    if output.is_symlink() or (output.exists() and (not output.is_dir() or not (output/'manifest.json').is_file())):
        raise ValueError('répertoire de sortie existant non reconnu ; choisir un autre chemin')
    if output.exists():
        old = json.loads((output/'manifest.json').read_text(encoding='utf-8'))
        if old.get('format') != 'nginx-country-combined-v1':
            raise ValueError('répertoire de sortie non reconnu')
    bases, meta = {}, {}
    for source in ('ipverse', 'ipdeny'):
        bases[source], meta[source] = _load(input_root, source)
    if any(meta[s].get('policy') != 'keep' or meta[s].get('special_policy_version') != 1 for s in meta):
        raise ValueError('générations sources incompatibles avec la politique keep version 1')
    geo = load_geolite(archive)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.nginx-country-', dir=output.parent))
    backup = None
    try:
        entries = {}
        for country in sorted(ISO_COUNTRIES):
            inputs = {source: _read_country(bases[source], meta[source], country) for source in ('ipverse','ipdeny')}
            inputs['geolite'] = {key: {'status': 'present' if geo['countries'].get(country, {}).get(key) else 'absent', 'prefixes': geo['countries'].get(country, {}).get(key, [])} for key in ('ipv4','ipv6')}
            allow, deny, states = [], [], {}
            for family in (4, 6):
                key = 'ipv' + str(family)
                combined = combine_family({s: inputs[s][key] for s in SOURCES}, family)
                allow.extend(combined['allow'])
                deny.extend(combined['deny'])
                states[key] = {'status': combined['status'], 'sources': {s: inputs[s][key]['status'] for s in SOURCES}}
            entries[country] = states
            for action, networks in (('allow',allow),('deny',deny)):
                header = f"# {country} | {action} = {'union' if action == 'allow' else 'intersection'} IPverse, IPdeny, GeoLite\n# IPv4: {states['ipv4']['status']} | IPv6: {states['ipv6']['status']}\n"
                (stage/f'{country}-{action}.conf').write_text(header + ''.join(f'{action} {net};\n' for net in networks), encoding='utf-8')
        result = {'format':'nginx-country-combined-v1','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'policy':'keep','rule':{'allow':'union','deny':'intersection'},'sources':{s:{'generation':meta[s].get('generation'),'generated_at':meta[s].get('generated_at')} for s in meta},'geolite':{'archive':geo['archive'],'sha256':geo['sha256'],'country_field':'geoname_id','unknown_blocks':geo['unknown']},'countries':entries}
        (stage/'manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        if output.exists():
            backup = output.with_name('.' + output.name + '-previous-' + uuid.uuid4().hex)
            os.rename(output, backup)
        try:
            os.rename(stage, output)
        except OSError:
            if backup is not None:
                os.rename(backup, output)
            raise
        if backup is not None:
            shutil.rmtree(backup)
        return result
    finally:
        if stage.exists():
            shutil.rmtree(stage)
