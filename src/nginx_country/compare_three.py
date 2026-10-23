"""Comparaison indépendante de trois couvertures par pays et famille."""
from itertools import combinations

from .compare import _load, _read_country, _intervals, _intersection, _subtract, _count, _top_cidrs, compare_networks
from .countries import ISO_COUNTRIES
from .geolite import load_geolite

SOURCES = ('ipverse', 'ipdeny', 'geolite')


def compare_three_networks(ipverse, ipdeny, geolite, family):
    intervals = {name: _intervals(values, family) for name, values in zip(SOURCES, (ipverse, ipdeny, geolite))}
    a, b, c = (intervals[x] for x in SOURCES)
    triple = _intersection(_intersection(a, b), c)
    only = {name: _subtract(_subtract(intervals[name], intervals[others[0]]), intervals[others[1]]) for name in SOURCES for others in [tuple(x for x in SOURCES if x != name)]}
    pairs = {x + '_' + y: _subtract(_intersection(intervals[x], intervals[y]), intervals[next(z for z in SOURCES if z not in (x, y))]) for x, y in combinations(SOURCES, 2)}
    counts = {'all_three': _count(triple), 'only': {k: _count(v) for k, v in only.items()}, 'exactly_two': {k: _count(v) for k, v in pairs.items()}}
    counts['union'] = counts['all_three'] + sum(counts['only'].values()) + sum(counts['exactly_two'].values())
    counts['only_cidrs'] = {k: _top_cidrs(v, family) for k, v in only.items()}
    return counts


def rename_pair(data, left, right):
    return {(left + key[len('ipverse'):] if key.startswith('ipverse_') else right + key[len('ipdeny'):] if key.startswith('ipdeny_') else key): value for key, value in data.items()}


def compare_three(root, archive, country=None):
    metadata, bases = {}, {}
    for source in SOURCES[:2]:
        bases[source], metadata[source] = _load(root, source)
    if any(metadata['ipverse'].get(k) != metadata['ipdeny'].get(k) or metadata['ipverse'].get(k) is None for k in ('policy', 'special_policy_version')):
        raise ValueError('politiques de génération incompatibles')
    # Les comparaisons GeoLite exigent la même politique que la lecture brute.
    if metadata['ipverse']['policy'] != 'keep' or metadata['ipverse']['special_policy_version'] != 1:
        raise ValueError('GeoLite exige la politique keep version 1')
    geo = load_geolite(archive)
    codes = set(geo['countries']) | set(metadata['ipverse']['countries']) | set(metadata['ipdeny']['countries'])
    if not codes <= ISO_COUNTRIES:
        raise ValueError('code pays invalide')
    if country:
        country = country.upper()
        if country not in ISO_COUNTRIES or country not in codes:
            raise ValueError('pays inconnu')
        codes = {country}
    countries = {}
    for code in sorted(codes):
        inputs = {source: _read_country(bases[source], metadata[source], code) for source in SOURCES[:2]}
        inputs['geolite'] = {f: {'status': 'present' if geo['countries'].get(code, {}).get(f) else 'absent', 'prefixes': geo['countries'].get(code, {}).get(f, [])} for f in ('ipv4','ipv6')}
        families = {}
        for family in (4,6):
            key = 'ipv' + str(family)
            statuses = {s: inputs[s][key]['status'] for s in SOURCES}
            pairwise = {}
            for left, right in combinations(SOURCES, 2):
                pair = left + '_' + right
                if 'absent' in (statuses[left], statuses[right]):
                    pairwise[pair] = None
                else:
                    raw = compare_networks(inputs[left][key]['prefixes'], inputs[right][key]['prefixes'], family)
                    pairwise[pair] = rename_pair(raw, left, right)
            complete = all(statuses[s] != 'absent' for s in SOURCES)
            families[key] = {'status': statuses, 'pairwise': pairwise, 'three_way': compare_three_networks(*(inputs[s][key]['prefixes'] for s in SOURCES), family) if complete else None}
        countries[code] = families
    return {'generations': {s: {'id': metadata[s].get('generation'), 'generated_at': metadata[s].get('generated_at')} for s in SOURCES[:2]}, 'geolite': {'archive': geo['archive'], 'sha256': geo['sha256'], 'country_field': 'geoname_id', 'unknown_blocks': geo['unknown']}, 'policy': 'keep', 'countries': countries}
