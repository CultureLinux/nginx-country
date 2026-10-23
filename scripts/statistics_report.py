"""Graphiques descriptifs d'une comparaison, sans référence de vérité terrain."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


def summarize(report):
    countries = report['countries']
    result = {}
    for family in ('ipv4', 'ipv6'):
        values = []
        missing = undefined = 0
        for code, data in countries.items():
            item = data[family]
            if 'comparison' in item and item['comparison'] is None:
                missing += 1
            elif item.get('jaccard') is None:
                undefined += 1
            else:
                values.append((code, item['jaccard']))
        if any(not 0 <= value <= 1 for _, value in values):
            raise ValueError('indice de Jaccard hors limites')
        numbers = [value for _, value in values]
        result[family] = {'count': len(values), 'missing': missing, 'undefined': undefined, 'mean': statistics.mean(numbers) if numbers else None, 'median': statistics.median(numbers) if numbers else None, 'below_half': sum(v < .5 for v in numbers), 'at_least_90': sum(v >= .9 for v in numbers), 'values': values}
    return result


def make_charts(report, summary, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 140})
    colors = {'ipv4': '#187b9d', 'ipv6': '#c26b31'}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    bins = np.linspace(0, 100, 11)
    for ax, family in zip(axes, ('ipv4', 'ipv6')):
        row = summary[family]
        ax.hist([100*v for _, v in row['values']], bins=bins, color=colors[family], edgecolor='white')
        ax.axvline(row['median'] * 100, color='#202a35', linestyle='--', label=f"Médiane : {row['median']*100:.1f} %")
        ax.set(title=f"{family.upper()} — {row['count']} pays comparables", xlabel='Jaccard (%)', xlim=(0, 100))
        ax.legend(frameon=False)
    axes[0].set_ylabel('Nombre de pays')
    fig.suptitle('Accord entre IPverse et IPdeny, par pays', fontweight='bold')
    fig.tight_layout()
    fig.savefig(output/'accord-pays.png', bbox_inches='tight')
    plt.close(fig)

    fr = report['countries']['FR']
    fig, ax = plt.subplots(figsize=(9, 3.4))
    for y, family in enumerate(('ipv4', 'ipv6')):
        d = fr[family]
        counts = [d['intersection'], d['ipverse_only'], d['ipdeny_only']]
        left = 0
        for count, label, color in zip(counts, ('Commun', 'IPverse seul', 'IPdeny seul'), ('#187b9d', '#e3aa4c', '#c26b31')):
            width = count / d['union'] * 100
            ax.barh(y, width, left=left, color=color, label=label if y == 0 else None, height=.55)
            if width >= 3:
                ax.text(left+width/2, y, f'{width:.1f} %', ha='center', va='center', color='white' if color != '#e3aa4c' else '#202a35', fontsize=9)
            left += width
    ax.set(yticks=[0,1], yticklabels=['IPv4', 'IPv6'], xlabel="Part de l'union des adresses (%)", xlim=(0,100))
    ax.invert_yaxis()
    ax.legend(loc='lower center', bbox_to_anchor=(.5,-.52), ncol=3, frameon=False)
    ax.set_title('France : répartition de la couverture', fontweight='bold')
    fig.tight_layout()
    fig.savefig(output/'france-couverture.png', bbox_inches='tight')
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    for ax, family in zip(axes, ('ipv4', 'ipv6')):
        values = sorted(summary[family]['values'], key=lambda x: (x[1], x[0]))[:10]
        ax.barh([x[0] for x in values], [100*x[1] for x in values], color=colors[family])
        ax.invert_yaxis()
        ax.set(xlim=(0,100), xlabel='Jaccard (%)', title=family.upper())
    fig.suptitle('Dix accords les plus faibles par famille', fontweight='bold')
    fig.tight_layout()
    fig.savefig(output/'accords-faibles.png', bbox_inches='tight')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description='Produire les statistiques et graphiques descriptifs')
    parser.add_argument('--input', type=Path, default=Path('comparaison.json'))
    parser.add_argument('--output', type=Path, default=Path('docs/figures'))
    args = parser.parse_args()
    data = args.input.read_bytes()
    report = json.loads(data)
    summary = summarize(report)
    make_charts(report, summary, args.output)
    result = {'input_sha256': hashlib.sha256(data).hexdigest(), 'generations': report.get('generations'), 'policy': report.get('policy'), 'countries': len(report['countries']), 'families': {k: {key: value for key, value in row.items() if key != 'values'} for k, row in summary.items()}}
    (args.output/'statistiques.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
