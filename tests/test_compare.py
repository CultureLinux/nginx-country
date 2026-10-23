import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def generation(root, source, families, cidrs):
    p = Path(root) / source / 'latest'
    p.mkdir(parents=True)
    text = ''.join('allow ' + item + ';\n' for item in cidrs)
    (p/'FR-allow.conf').write_text('# test\n' + text)
    digest = hashlib.sha256(('\n'.join(cidrs) + '\n').encode()).hexdigest()
    (p/'manifest.json').write_text(json.dumps({'source': source, 'generation': 'test', 'policy':'keep', 'special_policy_version': 1, 'countries': {'FR': families}, 'content_sha256': {'FR':digest}}))


class CompareTests(unittest.TestCase):
    def test_partial_overlap_and_equivalent_cidrs(self):
        from nginx_country.compare import compare_networks
        r = compare_networks(['192.0.2.0/24'], ['192.0.2.0/25', '192.0.2.128/26'], 4)
        self.assertEqual((r['ipverse_addresses'], r['ipdeny_addresses'], r['intersection'], r['union']), (256,192,192,256))
        self.assertEqual(r['ipverse_only_cidrs'], ['192.0.2.192/26'])
        self.assertEqual(r['jaccard'], 0.75)
        self.assertEqual(compare_networks(['192.0.2.0/24'], ['192.0.2.0/25','192.0.2.128/25'], 4)['jaccard'], 1.0)

    def test_ipv6_and_empty_union(self):
        from nginx_country.compare import compare_networks
        self.assertEqual(compare_networks(['2001:db8::/32'], ['2001:db8::/33'], 6)['ipverse_only'], 2**95)
        self.assertIsNone(compare_networks([], [], 6)['jaccard'])

    def test_cli_identifies_absent_and_corrupted_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            fam = {'ipv4':'present','ipv6':'empty'}
            generation(tmp,'ipverse',fam,['192.0.2.0/24'])
            generation(tmp,'ipdeny',{'ipv4':'present','ipv6':'absent'},['192.0.2.0/25'])
            cmd=[sys.executable,'-m','nginx_country','compare','--input',tmp,'--country','FR']
            p=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            data=json.loads(p.stdout)
            self.assertEqual(data['countries']['FR']['ipv4']['intersection'],128)
            self.assertIsNone(data['countries']['FR']['ipv6']['comparison'])
            (Path(tmp)/'ipdeny/latest/FR-allow.conf').write_text('allow 0.0.0.0/0;\n')
            p=subprocess.run(cmd,capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0)

    def test_missing_source_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=subprocess.run([sys.executable,'-m','nginx_country','compare','--input',tmp],capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0)
