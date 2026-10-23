import argparse
import sys
from pathlib import Path

from .fetch import collect, collect_all


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'generate':
        from .generate import generate_all
        parser = argparse.ArgumentParser(description='Génération expérimentale de règles Nginx')
        parser.add_argument('--input', type=Path, default=Path('data/raw'))
        parser.add_argument('--output', type=Path, default=Path('generated'))
        parser.add_argument('--special', choices=('keep', 'exclude'), default='keep')
        parser.add_argument('--dry-run', action='store_true')
        args = parser.parse_args(sys.argv[2:])
        results = generate_all(args.input, args.output, args.special, args.dry_run)
        for source, result in results.items():
            print(f"{source}: " + (('simulation' if args.dry_run else result['path']) + f" ({result['countries']} pays)" if result['ok'] else 'échec : ' + result['error']))
        return 0 if all(result['ok'] for result in results.values()) else 1
    parser = argparse.ArgumentParser(description='Collecte expérimentale par pays')
    parser.add_argument('country', nargs='?', default='all', help='code pays à deux lettres, par exemple FR')
    parser.add_argument('--output', type=Path, default=Path('data/raw'), help='répertoire des données')
    args = parser.parse_args()
    try:
        results = collect_all(args.output) if args.country.lower() == 'all' else collect(args.country.upper(), args.output)
    except ValueError as exc:
        parser.error(str(exc))
    for source, result in results.items():
        print(f"{source}: " + (result['path'] if result['ok'] else 'échec : ' + result['error']))
    return 0 if all(result['ok'] for result in results.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
