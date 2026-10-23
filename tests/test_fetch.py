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
        import hashlib
        ipverse = b'{"countryCode":"FR","prefixes":{"ipv4":["192.0.2.0/24"],"ipv6":[]}}'
        blob = hashlib.sha1(b'blob ' + str(len(ipverse)).encode() + b'\0' + ipverse).hexdigest()
        tree = json.dumps({'truncated': False, 'tree': [{'path': 'country/fr/fr.json', 'type': 'blob', 'sha': blob}]}).encode()
        def downloader(url):
            if '/commits/master' in url:
                return json.dumps({'sha': 'a' * 40}).encode()
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
            if url.endswith('/MD5SUM'):
                import hashlib
                digest = hashlib.md5(b'192.0.2.0/24\n').hexdigest()
                return (f'd41d8cd98f00b204e9800998ecf8427e  aa-aggregated.zone\n{digest}  bb-aggregated.zone\n').encode()
            if 'aa-aggregated' in url:
                return b''
            return b'2001:db8::/32\n' if 'ipv6' in url else b'192.0.2.0/24\n'
        with tempfile.TemporaryDirectory() as tmp:
            result = collect_all(tmp, downloader)
            self.assertFalse(result['ipdeny']['ok'])
            self.assertFalse((Path(tmp) / 'ipdeny' / 'all').exists())
            self.assertEqual(len(list((Path(tmp) / 'ipdeny').glob('all-*/ipv4/bb-aggregated.zone'))), 1)

class CompletenessTests(unittest.TestCase):
    def test_special_empty_confirmed_by_checksum_is_kept_and_marked(self):
        from nginx_country.fetch import inspect_ipdeny_zone
        status = inspect_ipdeny_zone(b'', 4, 'AP', 'd41d8cd98f00b204e9800998ecf8427e')
        self.assertEqual(status, 'special-empty-confirmed')
        with self.assertRaises(ValueError):
            inspect_ipdeny_zone(b'', 4, 'FR', 'd41d8cd98f00b204e9800998ecf8427e')
        with self.assertRaises(ValueError):
            inspect_ipdeny_zone(b'', 4, 'AP', None)
        with self.assertRaises(ValueError):
            inspect_ipdeny_zone(b'192.0.2.0/24\n', 4, 'FR', '0' * 32)

    def test_disappearance_of_previous_file_blocks_update(self):
        from nginx_country.fetch import check_inventory
        old = {'files': [{'file': 'ipv4/fr-aggregated.zone'}, {'file': 'ipv6/fr-aggregated.zone'}]}
        with self.assertRaises(ValueError):
            check_inventory({'ipv4/fr-aggregated.zone'}, old)
        check_inventory({'ipv4/fr-aggregated.zone', 'ipv6/fr-aggregated.zone'}, old)

    def test_manifest_rejects_truncation_or_missing_checksum(self):
        from nginx_country.fetch import parse_checksums
        with self.assertRaises(ValueError):
            parse_checksums(b'd41d8cd98f00b204e9800998ecf8427e  fr-aggregated.zone\n', {'fr-aggregated.zone', 'de-aggregated.zone'})
        with self.assertRaises(ValueError):
            parse_checksums(b'bad manifest', {'fr-aggregated.zone'})

    def test_complete_ipdeny_with_confirmed_empty_special_zone_is_recorded(self):
        from nginx_country.fetch import collect_all
        def downloader(url):
            if 'api.github.com' in url:
                raise OSError('offline')
            if url.endswith('/aggregated/'):
                return b'<a href="ap-aggregated.zone">ap</a>' if 'ipv6' not in url else b'<a href="fr-aggregated.zone">fr</a>'
            if url.endswith('/MD5SUM'):
                return b'd41d8cd98f00b204e9800998ecf8427e  ap-aggregated.zone\n'
            return b'2001:db8::/32\n' if 'ipv6' in url else b''
        with tempfile.TemporaryDirectory() as tmp:
            result = collect_all(tmp, downloader)
            self.assertTrue(result['ipdeny']['ok'], result['ipdeny'])
            metadata = json.loads((Path(tmp) / 'ipdeny/all/metadata.json').read_text())
            self.assertEqual(metadata['files'][0]['status'], 'special-empty-confirmed')
            self.assertFalse(metadata['historical_reference'])

    def test_ipverse_uses_one_revision_and_checks_content(self):
        from nginx_country.fetch import collect_all
        import hashlib
        payload = b'{"countryCode":"FR","prefixes":{"ipv4":["192.0.2.0/24"],"ipv6":[]}}'
        blob = hashlib.sha1(b'blob ' + str(len(payload)).encode() + b'\0' + payload).hexdigest()
        commit = 'a' * 40
        def downloader(url):
            if '/commits/master' in url:
                return json.dumps({'sha': commit}).encode()
            if '/git/trees/' in url:
                self.assertIn(commit, url)
                return json.dumps({'truncated': False, 'tree': [{'path':'country/fr/fr.json', 'type':'blob', 'sha':blob}]}).encode()
            if 'githubusercontent' in url:
                self.assertIn('/' + commit + '/', url)
                return payload
            raise OSError('offline')
        with tempfile.TemporaryDirectory() as tmp:
            result = collect_all(tmp, downloader)
            self.assertTrue(result['ipverse']['ok'], result['ipverse'])
            metadata = json.loads((Path(tmp) / 'ipverse/all/metadata.json').read_text())
            self.assertEqual(metadata['revision'], commit)
