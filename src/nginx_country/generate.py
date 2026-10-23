"""Production de fichiers Nginx expérimentaux, sans activation."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from .datasets import load_dataset
from .normalize import normalize_cidrs, apply_special, find_overlaps


def generate_source(input_root, output_root, source, policy='keep', dry_run=False):
    dataset = load_dataset(input_root, source)
    normalized, countries, special_events = {}, {}, {}
    for code, families in sorted(dataset['countries'].items()):
        normalized[code] = {}
        countries[code] = {}
        for family in (4, 6):
            key = 'ipv' + str(family)
            countries[code][key] = families[key]['status']
            nets = normalize_cidrs(families[key]['prefixes'], family)
            nets, events = apply_special(nets, family, policy)
            normalized[code][key] = nets
            if events:
                special_events.setdefault(code, {})[key] = events
    overlaps = {key: find_overlaps({code: families[key] for code, families in normalized.items()}) for key in ('ipv4', 'ipv6')}
    if dry_run:
        return {'countries': len(countries), 'dry_run': True}
    parent = Path(output_root) / source
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.tmp-', dir=parent))
    version = 'generation-' + uuid.uuid4().hex
    try:
        stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        hashes = {}
        for code, families in normalized.items():
            prefixes = families['ipv4'] + families['ipv6']
            content = '\n'.join(prefixes) + '\n'
            hashes[code] = hashlib.sha256(content.encode()).hexdigest()
            for directive in ('allow', 'deny'):
                states = countries[code]
                header = f"# Source: {source} | Country: {code} | Generated: {stamp} | IPv4={states['ipv4']} IPv6={states['ipv6']} | Generation: {version}\n"
                rules = ''.join(f'{directive} {net};\n' for net in prefixes)
                (temporary / f'{code}-{directive}.conf').write_text(header + rules, encoding='utf-8')
        manifest = {'source': source, 'revision': dataset['revision'], 'generated_at': stamp, 'generation': version, 'historical_reference': dataset['historical_reference'], 'policy': policy, 'special_policy_version': 1, 'input_files': dataset['input_files'], 'countries': countries, 'special_codes': dataset['special_codes'], 'special_intersections': special_events, 'overlaps': overlaps, 'content_sha256': hashes}
        (temporary / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        final = parent / version
        os.rename(temporary, final)
        link = parent / 'latest'
        if link.exists() and not link.is_symlink():
            raise ValueError('destination latest non remplaçable')
        pending = parent / ('.link-' + uuid.uuid4().hex)
        try:
            pending.symlink_to(version, target_is_directory=True)
            os.replace(pending, link)
        finally:
            if pending.is_symlink():
                pending.unlink()
        return {'countries': len(countries), 'path': str(link)}
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def generate_all(input_root, output_root, policy='keep', dry_run=False):
    results = {}
    for source in ('ipverse', 'ipdeny'):
        try:
            results[source] = {'ok': True, **generate_source(input_root, output_root, source, policy, dry_run)}
        except (OSError, ValueError, TypeError, KeyError) as exc:
            results[source] = {'ok': False, 'error': str(exc)}
    return results
