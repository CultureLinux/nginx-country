import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def dataset(root, source, entries):
    directory = Path(root) / source / 'all'
    directory.mkdir(parents=True)
    files = []
    for name, country, contents in entries:
        data = contents.encode()
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        files.append({'file': name, 'country': country, 'category': 'country' if country in ('FR', 'DE') else 'special', 'status': 'valid', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'url': 'https://example.test/' + name})
    (directory / 'metadata.json').write_text(json.dumps({'source': source, 'revision': 'a' * 40 if source == 'ipverse' else None, 'scope': 'all-listed-unverified-completeness', 'errors': [], 'historical_reference': False, 'files': files}))


class DatasetTests(unittest.TestCase):
    def test_load_ipdeny_tracks_absent_family_and_rejects_corruption(self):
        from nginx_country.datasets import load_dataset
        with tempfile.TemporaryDirectory() as tmp:
            dataset(tmp, 'ipdeny', [('ipv4/fr-aggregated.zone', 'FR', '192.0.2.0/24\n')])
            loaded = load_dataset(tmp, 'ipdeny')
            self.assertEqual(loaded['countries']['FR']['ipv6']['status'], 'absent')
            (Path(tmp) / 'ipdeny/all/ipv4/fr-aggregated.zone').write_text('broken')
            with self.assertRaises(ValueError):
                load_dataset(tmp, 'ipdeny')

    def test_rejects_legacy_manifest(self):
        from nginx_country.datasets import load_dataset
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'ipverse/all'
            p.mkdir(parents=True)
            (p / 'metadata.json').write_text('{"source":"ipverse","files":[]}')
            with self.assertRaises(ValueError):
                load_dataset(tmp, 'ipverse')


class NormalizationTests(unittest.TestCase):
    def test_aggregation_family_and_special_exclusion(self):
        from nginx_country.normalize import normalize_cidrs, apply_special
        self.assertEqual(normalize_cidrs(['192.0.2.7/25', '192.0.2.128/25', '192.0.2.0/26'], 4), ['192.0.2.0/24'])
        with self.assertRaises(ValueError):
            normalize_cidrs(['2001:db8::/32'], 4)
        networks, events = apply_special(['10.0.0.0/7'], 4, 'exclude')
        self.assertEqual(networks, ['11.0.0.0/8'])
        self.assertEqual(events, ['10.0.0.0/8'])

    def test_country_overlaps_do_not_confuse_adjacent_ranges(self):
        from nginx_country.normalize import find_overlaps
        self.assertEqual(find_overlaps({'FR': ['192.0.2.0/24'], 'DE': ['192.0.2.128/25'], 'GB': ['192.0.3.0/24']}), [{'countries': ['DE', 'FR'], 'network': '192.0.2.128/25'}])


class GenerationTests(unittest.TestCase):
    def test_cli_generates_pairs_and_preserves_absent_family(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset(root / 'raw', 'ipdeny', [('ipv4/fr-aggregated.zone', 'FR', '192.0.2.0/25\n192.0.2.128/25\n')])
            run = subprocess.run([sys.executable, '-m', 'nginx_country', 'generate', '--input', str(root/'raw'), '--output', str(root/'out')], capture_output=True, text=True)
            self.assertEqual(run.returncode, 1, run.stderr)
            p = root/'out/ipdeny/latest'
            allow = (p/'FR-allow.conf').read_text()
            deny = (p/'FR-deny.conf').read_text()
            self.assertIn('IPv6=absent', allow)
            self.assertIn('allow 192.0.2.0/24;', allow)
            self.assertIn('deny 192.0.2.0/24;', deny)
            self.assertNotIn('deny all', deny)
            self.assertEqual(json.loads((p/'manifest.json').read_text())['countries']['FR']['ipv6'], 'absent')

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset(root/'raw', 'ipdeny', [('ipv4/fr-aggregated.zone', 'FR', '192.0.2.0/24\n')])
            subprocess.run([sys.executable, '-m', 'nginx_country', 'generate', '--input', str(root/'raw'), '--output', str(root/'out'), '--dry-run'], capture_output=True)
            self.assertFalse((root/'out').exists())

    def test_ipverse_pair_is_deterministic_and_missing_file_preserves_previous(self):
        from nginx_country.generate import generate_source
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = json.dumps({'countryCode':'FR','prefixes':{'ipv4':['192.0.2.7/24'],'ipv6':['2001:db8::/32']}})
            dataset(root/'raw', 'ipverse', [('fr.json', 'FR', payload)])
            generate_source(root/'raw', root/'out', 'ipverse')
            latest = root/'out/ipverse/latest'
            old = latest.resolve()
            m1 = json.loads((latest/'manifest.json').read_text())
            generate_source(root/'raw', root/'out', 'ipverse')
            m2 = json.loads((latest/'manifest.json').read_text())
            self.assertEqual(m1['content_sha256'], m2['content_sha256'])
            self.assertIn('allow 2001:db8::/32;', (latest/'FR-allow.conf').read_text())
            current = latest.resolve()
            self.assertNotEqual(old, current)
            (root/'raw/ipverse/all/fr.json').unlink()
            with self.assertRaises(OSError):
                generate_source(root/'raw', root/'out', 'ipverse')
            self.assertEqual(latest.resolve(), current)

    def test_ipv6_exclusion_subtracts_only_intersection(self):
        from nginx_country.normalize import apply_special
        nets, events = apply_special(['fc00::/6'], 6, 'exclude')
        self.assertEqual(nets, ['fe00::/9', 'fec0::/10'])
        self.assertIn('fc00::/7', events)
