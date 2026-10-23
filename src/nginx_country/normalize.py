"""Normalisation CIDR et signalement des réseaux particuliers."""
import heapq
import ipaddress

# Politique v1 : principales plages privées, locales, documentaires et réservées.
SPECIAL = {4: ('0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8', '169.254.0.0/16', '172.16.0.0/12', '192.0.0.0/24', '192.0.2.0/24', '192.168.0.0/16', '198.18.0.0/15', '198.51.100.0/24', '203.0.113.0/24', '224.0.0.0/4', '240.0.0.0/4'), 6: ('::/128', '::1/128', '::ffff:0:0/96', '64:ff9b:1::/48', '100::/64', '2001:db8::/32', 'fc00::/7', 'fe80::/10', 'ff00::/8')}


def normalize_cidrs(prefixes, family):
    if family not in (4, 6):
        raise ValueError('famille inconnue')
    networks = []
    for prefix in prefixes:
        if not isinstance(prefix, str) or '/' not in prefix:
            raise ValueError('CIDR invalide')
        net = ipaddress.ip_network(prefix, strict=False)
        if net.version != family:
            raise ValueError('famille incorrecte')
        networks.append(net)
    return [str(net) for net in ipaddress.collapse_addresses(networks)]


def apply_special(prefixes, family, policy):
    if policy not in ('keep', 'exclude') or family not in SPECIAL:
        raise ValueError('politique ou famille inconnue')
    special = [ipaddress.ip_network(item) for item in SPECIAL[family]]
    result, events = [], set()
    for item in prefixes:
        pieces = [ipaddress.ip_network(item)]
        for reserved in special:
            next_pieces = []
            for net in pieces:
                if not net.overlaps(reserved):
                    next_pieces.append(net)
                    continue
                intersection = net if net.subnet_of(reserved) else reserved
                events.add(str(intersection))
                if policy == 'keep':
                    next_pieces.append(net)
                elif net.subnet_of(reserved):
                    continue
                else:
                    next_pieces.extend(net.address_exclude(reserved))
            pieces = next_pieces
        result.extend(pieces)
    return [str(net) for net in ipaddress.collapse_addresses(result)], sorted(events, key=lambda n: (int(ipaddress.ip_network(n).network_address), ipaddress.ip_network(n).prefixlen))


def find_overlaps(countries):
    intervals = []
    for code, prefixes in countries.items():
        for prefix in prefixes:
            net = ipaddress.ip_network(prefix)
            intervals.append((net.version, int(net.network_address), int(net.broadcast_address), code))
    intervals.sort()
    results = set()
    for family in (4, 6):
        active = []
        for version, start, end, code in intervals:
            if version != family:
                continue
            while active and active[0][0] < start:
                heapq.heappop(active)
            for other_end, other_start, other_code in active:
                if code != other_code:
                    address = ipaddress.IPv4Address if family == 4 else ipaddress.IPv6Address
                    for net in ipaddress.summarize_address_range(address(max(start, other_start)), address(min(end, other_end))):
                        results.add((tuple(sorted((code, other_code))), str(net)))
            heapq.heappush(active, (end, start, code))
    return [{'countries': list(pair), 'network': net} for pair, net in sorted(results)]
