"""Comparer les ensembles d'adresses des générations retenues."""
import hashlib
import ipaddress
import json
from pathlib import Path
import re

from .countries import ISO_COUNTRIES
from .normalize import normalize_cidrs


def _intervals(prefixes, family):
    return [(int(n.network_address), int(n.broadcast_address)) for n in (ipaddress.ip_network(x) for x in normalize_cidrs(prefixes, family))]


def _intersection(a, b):
    i = j = 0
    result = []
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if lo <= hi:
            result.append((lo, hi))
        if a[i][1] <= b[j][1]:
            i += 1
        else:
            j += 1
    return result


def _subtract(a, b):
    result = []
    j = 0
    for start, end in a:
        while j < len(b) and b[j][1] < start:
            j += 1
        pos, k = start, j
        while k < len(b) and b[k][0] <= end:
            left, right = b[k]
            if left > pos:
                result.append((pos, min(end, left - 1)))
            pos = max(pos, right + 1)
            if pos > end:
                break
            k += 1
        if pos <= end:
            result.append((pos, end))
    return result


def _count(intervals):
    return sum(end - start + 1 for start, end in intervals)


def _top_cidrs(intervals, family, limit=10):
    address = ipaddress.IPv4Address if family == 4 else ipaddress.IPv6Address
    networks = (net for lo, hi in intervals for net in ipaddress.summarize_address_range(address(lo), address(hi)))
    # Rangés par taille décroissante, puis adresse ; l'ensemble n'est pas énuméré.
    import heapq
    top = heapq.nsmallest(limit, networks, key=lambda n: (-n.num_addresses, int(n.network_address)))
    return [str(n) for n in top]


def compare_networks(ipverse, ipdeny, family):
    left, right = _intervals(ipverse, family), _intervals(ipdeny, family)
    common = _intersection(left, right)
    left_only, right_only = _subtract(left, right), _subtract(right, left)
    lc, rc, ic = _count(left), _count(right), _count(common)
    union = lc + rc - ic
    return {'ipverse_prefixes': len(left), 'ipdeny_prefixes': len(right), 'ipverse_addresses': lc, 'ipdeny_addresses': rc, 'intersection': ic, 'union': union, 'ipverse_only': _count(left_only), 'ipdeny_only': _count(right_only), 'jaccard': ic / union if union else None, 'ipverse_only_cidrs': _top_cidrs(left_only, family), 'ipdeny_only_cidrs': _top_cidrs(right_only, family)}


def _load(root, source):
    base = (Path(root) / source / 'latest').resolve(strict=True)
    manifest = json.loads((base / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('source') != source or not isinstance(manifest.get('countries'), dict) or not manifest['countries'] or not isinstance(manifest.get('content_sha256'), dict):
        raise ValueError('manifeste de génération invalide : ' + source)
    return base, manifest


def _read_country(base, manifest, code):
    if code not in manifest['countries']:
        return {'ipv4': {'status': 'absent', 'prefixes': []}, 'ipv6': {'status': 'absent', 'prefixes': []}}
    states = manifest['countries'][code]
    if any(states.get(k) not in ('present', 'empty', 'absent') for k in ('ipv4', 'ipv6')):
        raise ValueError('état de famille invalide : ' + code)
    content = (base / (code + '-allow.conf')).read_text(encoding='utf-8')
    prefixes = []
    for line in content.splitlines():
        if line.startswith('#') or not line.strip():
            continue
        match = re.fullmatch(r'allow ([^\s;]+);', line)
        if not match:
            raise ValueError('directive invalide : ' + code)
        prefixes.append(match.group(1))
    digest = hashlib.sha256(('\n'.join(prefixes) + '\n').encode()).hexdigest()
    if digest != manifest['content_sha256'].get(code):
        raise ValueError('empreinte de génération incorrecte : ' + code)
    families = {'ipv4': [], 'ipv6': []}
    for prefix in prefixes:
        if '/' not in prefix:
            raise ValueError('CIDR invalide')
        net = ipaddress.ip_network(prefix, strict=True)
        families['ipv' + str(net.version)].append(prefix)
    for family in families:
        if states[family] in ('empty', 'absent') and families[family]:
            raise ValueError('famille incohérente : ' + code)
    return {k: {'status': states[k], 'prefixes': families[k]} for k in families}


def compare_generations(root, country=None):
    left_base, left_meta = _load(root, 'ipverse')
    right_base, right_meta = _load(root, 'ipdeny')
    if any(left_meta.get(k) != right_meta.get(k) or left_meta.get(k) is None for k in ('policy', 'special_policy_version')):
        raise ValueError('politiques de génération incompatibles')
    codes = set(left_meta['countries']) | set(right_meta['countries'])
    if not codes <= ISO_COUNTRIES:
        raise ValueError('code pays invalide dans le manifeste')
    if country:
        country = country.upper()
        if country not in ISO_COUNTRIES:
            raise ValueError('code pays ISO invalide')
        if country not in codes:
            raise ValueError('pays absent des deux générations')
        codes = {country}
    results = {}
    for code in sorted(codes):
        l, r = _read_country(left_base, left_meta, code), _read_country(right_base, right_meta, code)
        families = {}
        for family in (4, 6):
            key = 'ipv' + str(family)
            states = {'ipverse_status': l[key]['status'], 'ipdeny_status': r[key]['status']}
            if 'absent' in (l[key]['status'], r[key]['status']):
                states['comparison'] = None
            else:
                states.update(compare_networks(l[key]['prefixes'], r[key]['prefixes'], family))
            families[key] = states
        results[code] = families
    return {'generations': {'ipverse': left_meta.get('generation'), 'ipdeny': right_meta.get('generation')}, 'policy': left_meta['policy'], 'countries': results}
