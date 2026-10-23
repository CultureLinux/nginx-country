"""Graphiques descriptifs d'une comparaison à trois sources."""
import argparse
import json
from pathlib import Path
import statistics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=Path('data/comparaison-trois.json'))
    parser.add_argument('--output', type=Path, default=Path('docs/figures'))
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding='utf-8'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    args.output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 140})
    pairs = [('ipverse_ipdeny','IPverse / IPdeny'), ('ipverse_geolite','IPverse / GeoLite'), ('ipdeny_geolite','IPdeny / GeoLite')]
    fig, axes = plt.subplots(1,2,figsize=(11,4.6),sharey=True)
    for ax, family in zip(axes, ('ipv4','ipv6')):
        data = []
        for name, label in pairs:
            values = [entry[family]['pairwise'][name]['jaccard']*100 for entry in report['countries'].values() if entry[family]['pairwise'][name] is not None and entry[family]['pairwise'][name]['jaccard'] is not None]
            data.append(values)
        ax.boxplot(data, vert=False, showfliers=False)
        ax.set_yticks(range(1, len(pairs) + 1), [p[1] for p in pairs])
        ax.set(xlim=(0,100), xlabel='Jaccard (%)', title=family.upper())
        ax.grid(axis='x', alpha=.2)
        for i, values in enumerate(data,1):
            ax.text(2,i+.22,f'n={len(values)} · médiane {statistics.median(values):.1f} %',fontsize=8)
    fig.suptitle('Accord entre sources par pays',fontweight='bold')
    fig.tight_layout()
    fig.savefig(args.output/'trois-sources-accord.png',bbox_inches='tight')
    plt.close(fig)

    fig,ax=plt.subplots(figsize=(10,4.5))
    parts=[('all_three','Trois sources','#267a82'),('ipverse_ipdeny','IPverse + IPdeny','#7770a8'),('ipverse_geolite','IPverse + GeoLite','#a891bd'),('ipdeny_geolite','IPdeny + GeoLite','#4d9ab7'),('ipverse','IPverse seul','#d89f3d'),('ipdeny','IPdeny seul','#bc6650'),('geolite','GeoLite seul','#537a54')]
    for y,family in enumerate(('ipv4','ipv6')):
        d=report['countries']['FR'][family]['three_way']
        if d is None or not d['union']:
            raise ValueError('France sans comparaison à trois sources exploitable')
        amounts={'all_three':d['all_three'],**d['exactly_two'],**d['only']}
        left=0
        for key,label,color in parts:
            width=100*amounts[key]/d['union']
            ax.barh(y,width,left=left,color=color,label=label if y==0 else None,height=.55)
            if width>=5: ax.text(left+width/2,y,f'{width:.1f} %',ha='center',va='center',color='white',fontsize=9)
            left+=width
    ax.set(yticks=[0,1],yticklabels=['IPv4','IPv6'],xlim=(0,100),xlabel='Part de l’union des couvertures FR (%)')
    ax.invert_yaxis()
    ax.set_title('France : répartition de la couverture entre les trois sources',fontweight='bold')
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.22),ncol=3,frameon=False,fontsize=9)
    fig.tight_layout()
    fig.savefig(args.output/'trois-sources-france.png',bbox_inches='tight')
    plt.close(fig)


if __name__=='__main__':
    main()
