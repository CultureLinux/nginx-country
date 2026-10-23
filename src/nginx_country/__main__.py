import argparse
import sys
from pathlib import Path

from .fetch import collect, collect_all


def main():
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
