import json
import tempfile
import unittest
from pathlib import Path

from nginx_country.fetch import collect, validate_ipverse, validate_zone


class FetchTests(unittest.TestCase):
    def test_rejects_wrong_country_and_invalid_network(self):
        with self.assertRaises(ValueError):
            validate_ipverse(b'{"countryCode":"DE","prefixes":{"ipv4":[],"ipv6":[]}}', 'FR')
        with self.assertRaises(ValueError):
            validate_zone(b'not-a-cidr\n', 4)
        with self.assertRaises(ValueError):
            validate_zone(b'', 4)

    def test_sources_independent_and_failed_fetch_preserves_previous(self):
        ipverse = b'{"countryCode":"FR","prefixes":{"ipv4":["192.0.2.0/24"],"ipv6":["2001:db8::/32"]}}'
        def download(url):
            if 'github' in url:
                return ipverse
            raise OSError('unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / 'ipdeny' / 'FR' / 'ipv4.zone'
            old.parent.mkdir(parents=True)
            old.write_bytes(b'previous')
            results = collect('FR', Path(tmp), download)
            self.assertTrue(results['ipverse']['ok'])
            self.assertFalse(results['ipdeny']['ok'])
            self.assertEqual(old.read_bytes(), b'previous')
            meta = json.loads((Path(tmp) / 'ipverse' / 'FR' / 'metadata.json').read_text())
            self.assertEqual(meta['country'], 'FR')
            self.assertEqual(len(meta['files'][0]['sha256']), 64)


if __name__ == '__main__':
    unittest.main()

class AllCountriesTests(unittest.TestCase):
    def test_collects_independent_inventories_and_preserves_old_on_failure(self):
        from nginx_country.fetch import collect_all
        tree = b'{"truncated":false,"tree":[{"path":"country/fr/fr.json","type":"blob"}]}'
        ipverse = b'{"countryCode":"FR","prefixes":{"ipv4":["192.0.2.0/24"],"ipv6":[]}}'
        def downloader(url):
            if 'api.github.com' in url:
                return tree
            if 'githubusercontent' in url:
                return ipverse
            if 'ipv6' in url:
                return b'<a href="fr-aggregated.zone">fr</a>'
            if url.endswith('/aggregated/'):
                return b'<a href="fr-aggregated.zone">fr</a>'
            if 'ipdeny.com' in url:
                raise OSError('unavailable')
            raise AssertionError(url)
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / 'ipdeny' / 'all'
            old.mkdir(parents=True)
            (old / 'old').write_text('previous')
            result = collect_all(tmp, downloader)
            self.assertTrue(result['ipverse']['ok'])
            self.assertFalse(result['ipdeny']['ok'])
            self.assertTrue((Path(tmp) / 'ipverse' / 'all' / 'fr.json').exists())
            self.assertEqual((old / 'old').read_text(), 'previous')

    def test_ipdeny_keeps_downloading_after_empty_zone_without_promoting(self):
        from nginx_country.fetch import collect_all
        def downloader(url):
            if 'api.github.com' in url:
                raise OSError('offline')
            if url.endswith('/aggregated/'):
                return b'<a href="aa-aggregated.zone">aa</a><a href="bb-aggregated.zone">bb</a>'
            if 'aa-aggregated' in url:
                return b''
            return b'2001:db8::/32\n' if 'ipv6' in url else b'192.0.2.0/24\n'
        with tempfile.TemporaryDirectory() as tmp:
            result = collect_all(tmp, downloader)
            self.assertFalse(result['ipdeny']['ok'])
            self.assertFalse((Path(tmp) / 'ipdeny' / 'all').exists())
            self.assertEqual(len(list((Path(tmp) / 'ipdeny').glob('all-*/ipv4/bb-aggregated.zone'))), 1)
