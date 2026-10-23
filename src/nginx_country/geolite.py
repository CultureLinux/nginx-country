"""Lecture en flux de GeoLite Country CSV sans extraction de l'archive."""
import csv
import hashlib
import io
import ipaddress
from pathlib import Path
import zipfile

from .countries import ISO_COUNTRIES


def load_geolite(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    countries, unknown, unresolved, unknown_prefixes = {}, {}, {}, {}
    with zipfile.ZipFile(path) as archive:
        def reader(suffix):
            names = [i for i in archive.infolist() if i.filename.endswith('/' + suffix)]
            if len(names) != 1 or names[0].file_size > 250_000_000:
                raise ValueError('fichier GeoLite manquant, dupliqué ou trop volumineux : ' + suffix)
            return io.TextIOWrapper(archive.open(names[0]), encoding='utf-8-sig', newline='')
        with reader('GeoLite2-Country-Locations-en.csv') as f:
            rows = csv.DictReader(f)
            if not {'geoname_id', 'country_iso_code'} <= set(rows.fieldnames or []):
                raise ValueError('colonnes de localisation absentes')
            locations = {}
            for row in rows:
                ident, code = row['geoname_id'], row['country_iso_code']
                if not ident or ident in locations:
                    raise ValueError('identifiant GeoLite invalide ou dupliqué')
                locations[ident] = code
        for family in (4, 6):
            key = 'ipv' + str(family)
            unknown[key] = unresolved[key] = 0
            unknown_prefixes[key] = []
            with reader(f'GeoLite2-Country-Blocks-IPv{family}.csv') as f:
                rows = csv.DictReader(f)
                if not {'network', 'geoname_id'} <= set(rows.fieldnames or []):
                    raise ValueError('colonnes de blocs absentes')
                for row in rows:
                    net = ipaddress.ip_network(row['network'], strict=True)
                    if net.version != family:
                        raise ValueError('famille GeoLite incorrecte')
                    ident = row['geoname_id']
                    if ident and ident not in locations:
                        unresolved[key] += 1
                        raise ValueError('identifiant GeoLite sans localisation : ' + ident)
                    code = locations.get(ident, '')
                    if code not in ISO_COUNTRIES:
                        unknown[key] += 1
                        unknown_prefixes[key].append(str(net))
                        continue
                    countries.setdefault(code, {'ipv4': [], 'ipv6': []})[key].append(str(net))
    if not countries:
        raise ValueError('aucun pays dans GeoLite')
    return {'countries': countries, 'unknown': unknown, 'unknown_prefixes': unknown_prefixes, 'sha256': digest.hexdigest(), 'archive': path.name}
