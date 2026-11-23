"""Téléchargement de l'archive GeoLite2 Country CSV (compte MaxMind gratuit)."""
import base64
import datetime
import os
from pathlib import Path
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from zipfile import BadZipFile

from .geolite import load_geolite

GEOLITE_URL = 'https://download.maxmind.com/geoip/databases/GeoLite2-Country-CSV/download?suffix=zip'
ARCHIVE = re.compile(r'GeoLite2-Country-CSV_(\d{8})\.zip')
MAX_BYTES = 250_000_000
_LOOPBACK = ('127.0.0.1', 'localhost', '::1')


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def credentials_from_env(environ=None):
    environ = os.environ if environ is None else environ
    account = (environ.get('MAXMIND_ACCOUNT_ID') or '').strip()
    key = (environ.get('MAXMIND_LICENSE_KEY') or '').strip()
    if not account or not key:
        raise ValueError('identifiants MaxMind manquants : définir MAXMIND_ACCOUNT_ID et MAXMIND_LICENSE_KEY (fichier .env)')
    return account, key


def _check_url(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme == 'https' or (parts.scheme == 'http' and parts.hostname in _LOOPBACK):
        return
    raise ValueError('HTTPS requis')


def _fetch(url, headers):
    """Une requête sans suivi automatique des redirections ; renvoie (corps, en-têtes) ou l'URL de redirection."""
    _check_url(url)
    request = urllib.request.Request(url, headers={'User-Agent': 'nginx-country', **headers})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=60) as response:
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError('archive GeoLite trop volumineuse')
            return body, response.headers, None
    except urllib.error.HTTPError as exc:
        exc.close()
        if exc.code in (301, 302, 303, 307, 308) and exc.headers.get('Location'):
            return None, None, urllib.parse.urljoin(url, exc.headers['Location'])
        hint = ' (identifiants refusés)' if exc.code in (401, 403) else ''
        raise ValueError(f'MaxMind a répondu HTTP {exc.code}{hint}') from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ValueError('téléchargement GeoLite impossible : ' + type(exc).__name__) from None


def download_geolite(account, key, output, url=GEOLITE_URL):
    """Télécharge, valide puis promeut l'archive ; supprime les anciennes archives GeoLite."""
    output = Path(output)
    token = base64.b64encode(f'{account}:{key}'.encode()).decode()
    headers = {'Authorization': 'Basic ' + token}
    for _ in range(4):
        body, response_headers, redirect = _fetch(url, headers)
        if redirect is None:
            break
        url, headers = redirect, {}  # l'URL signée ne reçoit jamais les identifiants
    else:
        raise ValueError('trop de redirections')
    match = ARCHIVE.search(response_headers.get('Content-Disposition') or '')
    name = match.group(0) if match else f'GeoLite2-Country-CSV_{datetime.date.today():%Y%m%d}.zip'
    output.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix='.geolite-', suffix='.tmp', dir=output)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(body)
        try:
            load_geolite(tmp)
        except (BadZipFile, KeyError, OSError) as exc:
            raise ValueError('archive GeoLite invalide : ' + type(exc).__name__) from None
        final = output / name
        os.replace(tmp, final)
    finally:
        tmp.unlink(missing_ok=True)
    for old in output.iterdir():
        if old != final and ARCHIVE.fullmatch(old.name):
            old.unlink()
    return final


def latest_geolite(directory):
    archives = sorted(p for p in Path(directory).glob('GeoLite2-Country-CSV_*.zip') if ARCHIVE.fullmatch(p.name))
    if not archives:
        raise ValueError(f'aucune archive GeoLite dans {directory} : lancer collect-geolite')
    return archives[-1]
