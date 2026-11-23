"""Interface en ligne de commande : collect, collect-geolite, generate, compare, compare-three, build-combined, update."""
import argparse
import json
import sys
from pathlib import Path
from zipfile import BadZipFile

COMMANDS = ('collect', 'collect-geolite', 'generate', 'compare', 'compare-three', 'build-combined', 'update')
ERRORS = (OSError, ValueError, KeyError, TypeError, BadZipFile)


def build_parser():
    parser = argparse.ArgumentParser(prog='nginx_country', description='Règles Nginx par pays à partir d\'IPverse, IPdeny et GeoLite.')
    sub = parser.add_subparsers(dest='command', metavar='commande', required=True)

    collect = sub.add_parser('collect', help='télécharger les données brutes (tous les pays par défaut)')
    collect.add_argument('country', nargs='?', default='all', help='code pays à deux lettres, par exemple FR')
    collect.add_argument('--output', type=Path, default=Path('data/raw'), help='répertoire des données')

    geolite = sub.add_parser('collect-geolite', help='télécharger GeoLite2 Country CSV (identifiants MaxMind dans .env)')
    geolite.add_argument('--env-file', type=Path, default=Path('.env'))
    geolite.add_argument('--output', type=Path, default=Path('data/raw/geolite'))

    generate = sub.add_parser('generate', help='générer les règles Nginx de chaque source')
    generate.add_argument('--input', type=Path, default=Path('data/raw'))
    generate.add_argument('--output', type=Path, default=Path('generated'))
    generate.add_argument('--special', choices=('keep', 'exclude'), default='keep', help='plages spéciales : conserver ou exclure')
    generate.add_argument('--dry-run', action='store_true')

    compare = sub.add_parser('compare', help='comparer IPverse et IPdeny')
    compare.add_argument('--input', type=Path, default=Path('generated'))
    compare.add_argument('--country', help='code pays ISO, par exemple FR')

    three = sub.add_parser('compare-three', help='comparer IPverse, IPdeny et GeoLite')
    three.add_argument('--input', type=Path, default=Path('generated'))
    three.add_argument('--geolite', type=Path, required=True, help='archive GeoLite2 Country CSV (.zip)')
    three.add_argument('--country', help='code pays ISO, par exemple FR')

    combined = sub.add_parser('build-combined', help='produire les fichiers publiés (allow = union, deny = intersection)')
    combined.add_argument('--input', type=Path, default=Path('generated'))
    combined.add_argument('--geolite', type=Path, help='archive GeoLite2 Country CSV (.zip) ; par défaut la plus récente de --geolite-dir')
    combined.add_argument('--geolite-dir', type=Path, default=Path('data/raw/geolite'))
    combined.add_argument('--output', type=Path, default=Path('nginx-country'))

    update = sub.add_parser('update', help='tout mettre à jour : collecte des 3 sources, génération, fichiers publiés')
    update.add_argument('--skip-fetch', action='store_true', help='ne pas télécharger, réutiliser data/raw')
    update.add_argument('--env-file', type=Path, default=Path('.env'))
    update.add_argument('--data', type=Path, default=Path('data/raw'))
    update.add_argument('--generated', type=Path, default=Path('generated'))
    update.add_argument('--output', type=Path, default=Path('nginx-country'))
    return parser


def run_collect(args, parser):
    from .fetch import collect, collect_all
    try:
        results = collect_all(args.output) if args.country.lower() == 'all' else collect(args.country.upper(), args.output)
    except ValueError as exc:
        parser.error(str(exc))
    for source, result in results.items():
        print(f"{source}: " + (result['path'] if result['ok'] else 'échec : ' + result['error']))
    return 0 if all(result['ok'] for result in results.values()) else 1


def run_generate(args, parser):
    from .generate import generate_all
    results = generate_all(args.input, args.output, args.special, args.dry_run)
    for source, result in results.items():
        if result['ok']:
            print(f"{source}: " + ('simulation' if args.dry_run else result['path']) + f" ({result['countries']} pays)")
        else:
            print(f"{source}: échec : " + result['error'])
    return 0 if all(result['ok'] for result in results.values()) else 1


def run_compare(args, parser):
    from .compare import compare_generations
    try:
        report = compare_generations(args.input, args.country)
    except ERRORS as exc:
        print(f'comparaison impossible : {exc}', file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def run_compare_three(args, parser):
    from .compare_three import compare_three
    try:
        report = compare_three(args.input, args.geolite, args.country)
    except ERRORS as exc:
        print(f'comparaison impossible : {exc}', file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def run_collect_geolite(args, parser):
    from .env import load_env
    from .geolite_download import credentials_from_env, download_geolite
    load_env(args.env_file)
    try:
        path = download_geolite(*credentials_from_env(), args.output)
    except ValueError as exc:
        print(f'collecte GeoLite impossible : {exc}', file=sys.stderr)
        return 1
    print(f'geolite: {path}')
    return 0


def run_build_combined(args, parser):
    from .combined import build_combined
    from .geolite_download import latest_geolite
    try:
        archive = args.geolite or latest_geolite(args.geolite_dir)
        result = build_combined(args.input, archive, args.output)
    except ERRORS as exc:
        print(f'génération impossible : {exc}', file=sys.stderr)
        return 1
    states = [state[family]['status'] for state in result['countries'].values() for family in ('ipv4', 'ipv6')]
    print(f"{args.output} : {len(result['countries'])} pays ; {states.count('partial')} familles partielles (deny omis), "
          f"{states.count('absent')} absentes de toutes les sources (voir manifest.json)")
    return 0


def run_update(args, parser):
    """collect → collect-geolite → generate → build-combined ; s'arrête au premier échec."""
    steps = []
    if not args.skip_fetch:
        steps += [('collect', run_collect, argparse.Namespace(country='all', output=args.data)),
                  ('collect-geolite', run_collect_geolite, argparse.Namespace(env_file=args.env_file, output=args.data / 'geolite'))]
    steps += [('generate', run_generate, argparse.Namespace(input=args.data, output=args.generated, special='keep', dry_run=False)),
              ('build-combined', run_build_combined, argparse.Namespace(input=args.generated, geolite=None, geolite_dir=args.data / 'geolite', output=args.output))]
    for name, handler, namespace in steps:
        print(f'== {name}')
        code = handler(namespace, parser)
        if code:
            print(f'update interrompu : {name} a échoué', file=sys.stderr)
            return code
    return 0


HANDLERS = {'collect': run_collect, 'collect-geolite': run_collect_geolite, 'update': run_update, 'generate': run_generate, 'compare': run_compare,
            'compare-three': run_compare_three, 'build-combined': run_build_combined}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Compatibilité : « python -m nginx_country FR » équivaut à « collect FR ».
    if argv and argv[0] not in COMMANDS and (argv[0].isupper() or argv[0].lower() == 'all'):
        argv.insert(0, 'collect')
    parser = build_parser()
    args = parser.parse_args(argv)
    return HANDLERS[args.command](args, parser)


if __name__ == '__main__':
    sys.exit(main())
