import csv
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


def archive(path):
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('d/GeoLite2-Country-Locations-en.csv','geoname_id,country_iso_code\n1,FR\n2,DE\n3,\n')
        z.writestr('d/GeoLite2-Country-Blocks-IPv4.csv','network,geoname_id,registered_country_geoname_id\n192.0.2.0/25,1,2\n192.0.2.128/25,,1\n198.51.100.0/24,3,1\n')
        z.writestr('d/GeoLite2-Country-Blocks-IPv6.csv','network,geoname_id,registered_country_geoname_id\n2001:db8::/32,1,2\n')


class GeoLiteTests(unittest.TestCase):
    def test_geolocation_and_unknown_without_registration_fallback(self):
        from nginx_country.geolite import load_geolite
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'geo.zip'; archive(path)
            result=load_geolite(path)
            self.assertEqual(result['countries']['FR']['ipv4'], ['192.0.2.0/25'])
            self.assertEqual(result['unknown']['ipv4'], 2)
            self.assertNotIn('DE',result['countries'])

    def test_invalid_unresolved_id_fails(self):
        from nginx_country.geolite import load_geolite
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'geo.zip'; archive(path)
            with zipfile.ZipFile(path,'a') as z:
                z.writestr('other/GeoLite2-Country-Locations-en.csv','')
            with self.assertRaises(ValueError): load_geolite(path)

    def test_three_way_partition_exact(self):
        from nginx_country.compare_three import compare_three_networks
        r=compare_three_networks(['192.0.2.0/24'],['192.0.2.0/25'],['192.0.2.64/26'],4)
        self.assertEqual(r['union'],256)
        self.assertEqual(r['all_three'],64)
        self.assertEqual(r['exactly_two']['ipverse_ipdeny'],64)
        self.assertEqual(r['only']['ipverse'],128)
        self.assertEqual(sum(r['only'].values())+sum(r['exactly_two'].values())+r['all_three'],256)

    def test_pairwise_labels_preserve_both_sources(self):
        from nginx_country.compare_three import rename_pair
        result = rename_pair({'ipverse_addresses': 256, 'ipdeny_addresses': 128, 'ipverse_only_cidrs': ['192.0.2.128/25']}, 'ipdeny', 'geolite')
        self.assertEqual(result['ipdeny_addresses'], 256)
        self.assertEqual(result['geolite_addresses'], 128)
        self.assertEqual(result['ipdeny_only_cidrs'], ['192.0.2.128/25'])

    def test_compare_three_cli_with_real_generation(self):
        import subprocess,sys
        from test_generate import dataset
        from nginx_country.generate import generate_source
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive(root/'geo.zip')
            payload=json.dumps({'countryCode':'FR','prefixes':{'ipv4':['192.0.2.0/24'],'ipv6':['2001:db8::/32']}})
            dataset(root/'raw','ipverse',[('fr.json','FR',payload)])
            dataset(root/'raw','ipdeny',[('ipv4/fr-aggregated.zone','FR','192.0.2.0/25\n')])
            for source in ('ipverse','ipdeny'):
                generate_source(root/'raw',root/'generated',source)
            run=subprocess.run([sys.executable,'-m','nginx_country','compare-three','--input',str(root/'generated'),'--geolite',str(root/'geo.zip'),'--country','FR'],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            report=json.loads(run.stdout)
            d=report['countries']['FR']['ipv4']
            self.assertEqual(d['three_way']['all_three'],128)
            self.assertEqual(d['pairwise']['ipdeny_geolite']['jaccard'],1.0)
            self.assertIsNone(report['countries']['FR']['ipv6']['three_way'])

    def test_invalid_zip_is_reported_without_traceback(self):
        import subprocess,sys
        from test_generate import dataset
        from nginx_country.generate import generate_source
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            payload=json.dumps({'countryCode':'FR','prefixes':{'ipv4':['192.0.2.0/24'],'ipv6':[]}})
            dataset(root/'raw','ipverse',[('fr.json','FR',payload)])
            dataset(root/'raw','ipdeny',[('ipv4/fr-aggregated.zone','FR','192.0.2.0/24\n')])
            for source in ('ipverse','ipdeny'): generate_source(root/'raw',root/'generated',source)
            (root/'bad.zip').write_bytes(b'invalid')
            result=subprocess.run([sys.executable,'-m','nginx_country','compare-three','--input',str(root/'generated'),'--geolite',str(root/'bad.zip')],capture_output=True,text=True)
            self.assertEqual(result.returncode,1)
            self.assertNotIn('Traceback',result.stderr)
