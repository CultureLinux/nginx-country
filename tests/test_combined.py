import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from test_generate import dataset
from test_geolite import archive
from nginx_country.generate import generate_source


class CombinedTests(unittest.TestCase):
    def _build(self, root, ipverse_payload, ipdeny_files):
        from nginx_country.combined import build_combined
        archive(root/'geo.zip')
        dataset(root/'raw','ipverse',[('fr.json','FR',ipverse_payload)])
        dataset(root/'raw','ipdeny',ipdeny_files)
        for source in ('ipverse','ipdeny'): generate_source(root/'raw',root/'generated',source)
        return build_combined(root/'generated',root/'geo.zip',root/'nginx-country')

    def test_union_and_intersection_when_all_sources_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            payload=json.dumps({'countryCode':'FR','prefixes':{'ipv4':['192.0.2.0/24'],'ipv6':[]}})
            report=self._build(root,payload,[('ipv4/fr-aggregated.zone','FR','192.0.2.0/26\n')])
            allow=(root/'nginx-country/FR-allow.conf').read_text()
            deny=(root/'nginx-country/FR-deny.conf').read_text()
            self.assertIn('allow 192.0.2.0/24;',allow)
            self.assertIn('deny 192.0.2.0/26;',deny)
            self.assertEqual(report['countries']['FR']['ipv4']['status'],'complete')
            self.assertNotIn('deny all;',deny)
            self.assertNotIn('Experimental',allow)

    def test_missing_source_family_keeps_union_allow_and_omits_deny(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            payload=json.dumps({'countryCode':'FR','prefixes':{'ipv4':['192.0.2.0/24'],'ipv6':['2001:db8::/32']}})
            report=self._build(root,payload,[('ipv4/fr-aggregated.zone','FR','192.0.2.0/26\n')])
            allow=(root/'nginx-country/FR-allow.conf').read_text()
            deny=(root/'nginx-country/FR-deny.conf').read_text()
            self.assertIn('allow 2001:db8::/32;',allow)
            self.assertNotIn('2001:db8',deny)
            self.assertEqual(report['countries']['FR']['ipv6']['status'],'partial')
            self.assertEqual(report['countries']['FR']['ipv6']['sources']['ipdeny'],'absent')

    def test_family_absent_from_every_source_produces_no_rule(self):
        from nginx_country.combined import combine_family
        result=combine_family({'ipverse':{'status':'absent','prefixes':[]},'ipdeny':{'status':'absent','prefixes':[]},'geolite':{'status':'absent','prefixes':[]}},6)
        self.assertEqual(result,{'status':'absent','allow':[],'deny':[]})

    def test_empty_source_is_still_a_present_source(self):
        from nginx_country.combined import combine_family
        result=combine_family({'ipverse':{'status':'empty','prefixes':[]},'ipdeny':{'status':'present','prefixes':['192.0.2.0/24']},'geolite':{'status':'present','prefixes':['192.0.2.0/25']}},4)
        self.assertEqual(result['status'],'complete')
        self.assertEqual(result['allow'],['192.0.2.0/24'])
        self.assertEqual(result['deny'],[])

    def test_rebuild_leaves_no_backup_directory_behind(self):
        from nginx_country.combined import build_combined
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            payload=json.dumps({'countryCode':'FR','prefixes':{'ipv4':['192.0.2.0/24'],'ipv6':[]}})
            self._build(root,payload,[('ipv4/fr-aggregated.zone','FR','192.0.2.0/26\n')])
            build_combined(root/'generated',root/'geo.zip',root/'nginx-country')
            self.assertEqual(sorted(p.name for p in root.iterdir() if p.name.startswith('.')),[])

    def test_refuses_to_replace_unowned_directory(self):
        from nginx_country.combined import build_combined
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'output').mkdir(); (root/'output/user-file').write_text('keep')
            with self.assertRaises((OSError, ValueError)):
                build_combined(root/'missing',root/'bad.zip',root/'output')
            self.assertEqual((root/'output/user-file').read_text(),'keep')
