"""Collecte expérimentale de données par pays, sans promotion en production."""
import datetime
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import time
import urllib.request
import uuid

from .countries import ISO_COUNTRIES


def download(url):
    if not url.startswith('https://'):
        raise ValueError('HTTPS requis')
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'nginx-country/0.1'})
            with urllib.request.urlopen(request, timeout=30) as response:
                if not response.geturl().startswith('https://'):
                    raise ValueError('redirection non HTTPS')
                return response.read()
        except (OSError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def validate_zone(data, family):
    lines = data.decode('utf-8').splitlines()
    entries = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith('#')]
    if not entries:
        raise ValueError('liste vide')
    for entry in entries:
        if '/' not in entry or ipaddress.ip_network(entry, strict=False).version != family:
            raise ValueError('CIDR ou famille incorrects')


def validate_ipverse(data, country):
    obj = json.loads(data)
    if not isinstance(obj, dict) or obj.get('countryCode') != country or not isinstance(obj.get('prefixes'), dict):
        raise ValueError('schéma ou pays incorrect')
    total = 0
    for key, family in [('ipv4', 4), ('ipv6', 6)]:
        values = obj['prefixes'].get(key)
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise ValueError('liste de préfixes incorrecte')
        if values:
            validate_zone(('\n'.join(values)).encode(), family)
        total += len(values)
    if not total:
        raise ValueError('listes vides')


def collect(country, root, downloader=download):
    if not re.fullmatch(r'[A-Z]{2}', country):
        raise ValueError('le pays doit être un code à deux lettres majuscules')
    code = country.lower()
    sources = {
        'ipverse': [('country.json', f'https://raw.githubusercontent.com/ipverse/geo-ip-blocks/master/country/{code}/{code}.json', None)],
        'ipdeny': [('ipv4.zone', f'https://www.ipdeny.com/ipblocks/data/aggregated/{code}-aggregated.zone', 4),
                   ('ipv6.zone', f'https://www.ipdeny.com/ipv6/ipaddresses/aggregated/{code}-aggregated.zone', 6)],
    }
    results = {}
    for source, files in sources.items():
        try:
            payloads = []
            for index, (name, url, family) in enumerate(files):
                if source == 'ipdeny' and index and downloader is download:
                    time.sleep(1)
                data = downloader(url)
                if family is None:
                    validate_ipverse(data, country)
                else:
                    validate_zone(data, family)
                payloads.append((name, url, data))
            parent = Path(root) / source
            parent.mkdir(parents=True, exist_ok=True)
            directory = parent / (country + '-' + uuid.uuid4().hex)
            directory.mkdir()
            records = []
            for name, url, data in payloads:
                (directory / name).write_bytes(data)
                records.append({'file': name, 'url': url, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
            metadata = {'source': source, 'country': country, 'fetched_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'scope': 'single-country-unverified-completeness', 'files': records}
            (directory / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
            link = parent / country
            if link.exists() and not link.is_symlink():
                raise ValueError('la destination existe et ne peut pas être remplacée')
            temporary = parent / ('.link-' + uuid.uuid4().hex)
            temporary.symlink_to(directory.name, target_is_directory=True)
            os.replace(temporary, link)
            results[source] = {'ok': True, 'path': str(link)}
        except (OSError, ValueError, UnicodeError, TypeError) as exc:
            results[source] = {'ok': False, 'error': str(exc)}
    return results



def parse_checksums(data, names):
    checksums = {}
    for line in data.decode('utf-8').splitlines():
        match = re.fullmatch(r'([0-9a-fA-F]{32}) [ *]([a-z]{2}-aggregated\.zone)', line)
        if not match or match.group(2) in checksums:
            raise ValueError('manifeste MD5 invalide')
        checksums[match.group(2)] = match.group(1).lower()
    if set(checksums) != set(names):
        raise ValueError('inventaire IPv4 et manifeste MD5 différents')
    return checksums


def inspect_ipdeny_zone(data, family, country, checksum=None):
    if checksum is not None and hashlib.md5(data).hexdigest() != checksum:
        raise ValueError('empreinte MD5 incorrecte')
    if not data and country == 'AP' and family == 4 and checksum is not None:
        return 'special-empty-confirmed'
    validate_zone(data, family)
    return 'valid'


def check_inventory(current, previous):
    missing = {item['file'] for item in previous['files']} - set(current)
    if missing:
        raise ValueError('fichiers disparus depuis la collecte précédente : ' + ', '.join(sorted(missing)))

def collect_all(root, downloader=download):
    """Collect inventories independently; publish only a fully downloaded source."""
    from html.parser import HTMLParser

    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.names = set()

        def handle_starttag(self, tag, attrs):
            if tag == 'a':
                href = dict(attrs).get('href', '')
                if re.fullmatch(r'[a-z]{2}-aggregated\.zone', href):
                    self.names.add(href)

    results = {}
    for source in ('ipverse', 'ipdeny'):
        try:
            files = []
            checksums = {}
            blob_hashes = {}
            revision = None
            if source == 'ipverse':
                commit_url = 'https://api.github.com/repos/ipverse/geo-ip-blocks/commits/master'
                revision = json.loads(downloader(commit_url)).get('sha')
                if not isinstance(revision, str) or not re.fullmatch(r'[0-9a-f]{40}', revision):
                    raise ValueError('révision IPverse invalide')
                url = f'https://api.github.com/repos/ipverse/geo-ip-blocks/git/trees/{revision}?recursive=1'
                tree = json.loads(downloader(url))
                if tree.get('truncated') or not isinstance(tree.get('tree'), list):
                    raise ValueError('inventaire IPverse incomplet')
                for item in tree['tree']:
                    match = re.fullmatch(r'country/([a-z]{2})/\1\.json', item.get('path', ''))
                    if match and item.get('type') == 'blob':
                        code = match.group(1)
                        blob = item.get('sha')
                        if not isinstance(blob, str) or not re.fullmatch(r'[0-9a-f]{40}', blob):
                            raise ValueError('empreinte IPverse absente')
                        blob_hashes[code + '.json'] = blob
                        files.append((code + '.json', f'https://raw.githubusercontent.com/ipverse/geo-ip-blocks/{revision}/' + item['path'], code.upper(), None))
            else:
                for family, base in ((4, 'https://www.ipdeny.com/ipblocks/data/aggregated/'), (6, 'https://www.ipdeny.com/ipv6/ipaddresses/aggregated/')):
                    links = Links()
                    links.feed(downloader(base).decode('utf-8'))
                    if not links.names:
                        raise ValueError('inventaire IPdeny vide')
                    if family == 4:
                        checksums = parse_checksums(downloader(base + 'MD5SUM'), links.names)
                    for name in sorted(links.names):
                        files.append((f'ipv{family}/' + name, base + name, name[:2].upper(), family))
            if not files:
                raise ValueError('inventaire vide')
            parent = Path(root) / source
            parent.mkdir(parents=True, exist_ok=True)
            previous_path = parent / 'all' / 'metadata.json'
            previous = json.loads(previous_path.read_text(encoding='utf-8')) if previous_path.exists() else None
            if previous is not None:
                check_inventory({item[0] for item in files}, previous)
            directory = parent / ('all-' + uuid.uuid4().hex)
            directory.mkdir()
            records = []
            errors = []
            for name, url, country, family in sorted(files):
                if source == 'ipdeny' and downloader is download:
                    time.sleep(1)
                data = downloader(url)
                status = 'valid'
                try:
                    if family is None:
                        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                        if blob != blob_hashes[name]:
                            raise ValueError('empreinte Git incorrecte')
                        validate_ipverse(data, country)
                    else:
                        status = inspect_ipdeny_zone(data, family, country, checksums.get(Path(name).name) if family == 4 else None)
                except (ValueError, UnicodeError) as exc:
                    status = 'invalid'
                    errors.append(f'{name}: {exc}')
                target = directory / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                records.append({'file': name, 'url': url, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'country': country, 'category': 'country' if country in ISO_COUNTRIES else 'special', 'status': status})
            metadata = {'revision': revision, 'historical_reference': previous is not None, 'errors': errors, 'source': source, 'fetched_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'scope': 'all-listed-unverified-completeness', 'files': records}
            (directory / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
            if errors:
                raise ValueError(f'données invalides dans {directory}: ' + '; '.join(errors))
            link = parent / 'all'
            if link.exists() and not link.is_symlink():
                raise ValueError('la destination existe et ne peut pas être remplacée')
            temporary = parent / ('.link-' + uuid.uuid4().hex)
            temporary.symlink_to(directory.name, target_is_directory=True)
            os.replace(temporary, link)
            results[source] = {'ok': True, 'path': str(link)}
        except (OSError, ValueError, UnicodeError, TypeError, KeyError) as exc:
            results[source] = {'ok': False, 'error': str(exc)}
    return results
