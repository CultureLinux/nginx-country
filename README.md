# nginx-country

Outil Python expérimental qui collecte les plages IP par pays d'IPverse et d'IPdeny, génère des règles Nginx distinctes et compare les couvertures. Il ne déploie ni ne recharge Nginx.

## Flux et commandes

Prérequis : Python 3.9 ou supérieur et un accès HTTPS pour la collecte. Depuis la racine du projet :

```bash
# Récupérer tous les pays ; IPdeny peut prendre plusieurs minutes.
PYTHONPATH=src python3 -m nginx_country

# Ou récupérer un seul pays.
PYTHONPATH=src python3 -m nginx_country FR

# Générer les règles des deux sources à partir des collectes retenues.
PYTHONPATH=src python3 -m nginx_country generate

# Comparer tous les pays ou seulement la France ; la sortie est en JSON.
PYTHONPATH=src python3 -m nginx_country compare > comparaison.json
PYTHONPATH=src python3 -m nginx_country compare --country FR

# Exécuter les tests hors ligne.
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Les données brutes sont sous `data/raw/<source>/all/` et les règles sous `generated/<source>/latest/`. Ces liens pointent vers les dernières versions retenues ; chaque source est traitée indépendamment et une erreur conserve sa version précédente. Les données et les règles générées sont ignorées par Git. Les commandes renvoient un code non nul si une source échoue.

La collecte vérifie les CIDR, les empreintes Git IPverse et le manifeste IPv4 IPdeny. Une collecte précédente sans les métadonnées requises doit être renouvelée avant génération. Le générateur conserve les plages particulières par défaut ; `generate --special exclude` retire celles de la liste versionnée du programme et les signale. `generate --dry-run` effectue une simulation. La liste des plages particulières n'est pas exhaustive. Les codes non ISO restent dans les données brutes et ne deviennent pas des fichiers pays.

La comparaison vérifie les empreintes des règles et exige des politiques de génération identiques. Elle calcule l'intersection, l'union et les différences d'adresses, et distingue une famille absente d'une famille vide. Les comptes IPv6 sont des entiers exacts ; l'indice de Jaccard est une approximation décimale. Consulter `--help` après `generate` ou `compare` pour les options de chemins. Le [cadrage des sources](docs/cadrage-sources.md) décrit les limites de collecte et les conditions d'utilisation.

## Construire les règles combinées

```bash
PYTHONPATH=src python3 -m nginx_country build-combined \
  --geolite data/raw/geolite/GeoLite2-Country-CSV_20261020.zip
```

La commande crée `nginx-country/XX-allow.conf` et `nginx-country/XX-deny.conf` pour chaque code ISO du projet, ainsi qu'un `manifest.json` traçant les sources et les familles incomplètes. **Règle de construction**, par pays et famille :

- `allow` contient l'**union** des couvertures IPverse, IPdeny et GeoLite : une adresse figure dans le fichier si au moins une source l'attribue au pays.
- `deny` contient leur **intersection** : une adresse figure dans le fichier seulement si les trois sources l'attribuent au pays.
- Si une famille manque dans au moins une source, elle est omise des deux fichiers ; le manifeste et l'en-tête indiquent `incomplete`. Une famille explicitement vide n'est pas une famille absente. La commande renvoie `1` si une famille est incomplète, même si elle a créé les fichiers.

L'absence d'une famille peut laisser passer ou bloquer du trafic selon les autres directives Nginx ; examiner le manifeste avant utilisation. Aucun fichier n'ajoute `deny all`. L'ordre des directives Nginx reste déterminant. La sortie est expérimentale, n'est pas activée et ne constitue pas une preuve de localisation ; une source attribuant à tort une plage au pays peut élargir l'autorisation. Le jeu utilise GeoLite et les conditions de sa licence s'appliquent. Les fichiers générés sont ignorés par Git. Un répertoire existant non reconnu n'est jamais remplacé ; lors d'une nouvelle construction, l'ancien jeu reconnu est conservé dans un répertoire `.nginx-country-previous-*`.

## Comparer avec GeoLite

La commande lit directement l'archive GeoLite Country CSV locale, sans l'extraire, et utilise `geoname_id` : le pays estimé de l'adresse, non le pays d'enregistrement. Elle traite les pays disponibles dans les trois sources ; les blocs sans pays identifiable restent dans l'archive et sont comptés comme inconnus. Une famille sans bloc pour un pays est indiquée absente, sans supposer une couverture vide.

```bash
PYTHONPATH=src python3 -m nginx_country compare-three \
  --geolite data/raw/geolite/GeoLite2-Country-CSV_20261020.zip \
  > data/comparaison-trois.json

# Restreindre la sortie à un pays ; l'archive entière est lue.
PYTHONPATH=src python3 -m nginx_country compare-three \
  --geolite data/raw/geolite/GeoLite2-Country-CSV_20261020.zip --country FR

# Produire les deux graphiques de comparaison à trois sources (Matplotlib requis).
python scripts/plot_three.py --input data/comparaison-trois.json
```

Le rapport contient, pour chaque pays et famille, les trois comparaisons par paires et une partition de l'union : trois sources, exactement deux sources, ou une seule. Les comparaisons à trois exigent la politique de plages spéciales `keep` version 1 pour les générations existantes. Les nombres sont des comptes d'adresses exacts, pas des nombres de visiteurs. Une adresse non classée FR par une source peut être attribuée à un autre pays ou être inconnue : le rapport ne fait pas cette distinction. Le résultat est dans `data/`, ignoré par Git.

Cette analyse utilise des données GeoLite créées par [MaxMind](https://www.maxmind.com), incluant des données [GeoNames](https://www.geonames.org) sous licence CC BY 4.0. L'utilisation et la redistribution de l'archive et des résultats dérivés sont soumises à la [licence GeoLite](https://www.maxmind.com/en/geolite/eula), notamment ses dispositions d'attribution et de mise à jour ; les conditions applicables doivent être examinées avant partage.

## Résultats statistiques et qualité des données

**Instantané étudié :** comparaison des générations du 23 octobre 2026, politique `keep`, 249 pays ou territoires. Les identifiants des générations et l'empreinte du fichier d'entrée sont conservés dans [statistiques.json](docs/figures/statistiques.json). Ces résultats et les figures sont un instantané : ils ne changent pas automatiquement avec les prochaines collectes.

**La qualité géographique ne peut pas être notée à partir de ces deux listes seules.** Leur accord mesure leur cohérence mutuelle, pas la proportion d'utilisateurs réellement situés dans le pays : les deux fournisseurs peuvent partager une même erreur. Une estimation de l'exactitude, des faux positifs et des faux négatifs nécessite une référence indépendante avec localisation connue, représentative du trafic et datée. Les plages par pays ne garantissent pas la localisation réelle ; des utilisateurs légitimes peuvent être bloqués.

| Indicateur descriptif | IPv4 | IPv6 |
|---|---:|---:|
| Pays comparables | 240 / 249 | 232 / 249 |
| Famille absente d'au moins une source | 9 | 17 |
| Jaccard médian par pays | 90,5 % | 93,7 % |
| Jaccard moyen par pays | 81,4 % | 84,6 % |
| Pays avec Jaccard inférieur à 50 % | 26 / 240 | 22 / 232 |

Jaccard = taille de l'intersection / taille de l'union. La moyenne et la médiane donnent le même poids à chaque pays, sans pondération par adresses ou trafic ; une union vide est exclue du calcul, comme les familles absentes. Les chiffres décrivent les données disponibles, sans intervalle de confiance ni estimation de l'exactitude. L'IPv6 mesure un espace d'adressage, pas un nombre d'utilisateurs.

![Distribution du Jaccard par pays en IPv4 et IPv6](docs/figures/accord-pays.png)

La distribution révèle une dispersion importante : le bon accord médian ne doit pas masquer les pays très divergents. Le graphique ci-dessous sélectionne les dix accords les plus faibles par famille, parmi les familles comparables ; un petit territoire pèse autant qu'un grand.

![Pays avec les accords les plus faibles](docs/figures/accords-faibles.png)

### France

| Mesure | IPv4 | IPv6 |
|---|---:|---:|
| Jaccard | 89,34 % | 95,18 % |
| Adresses IPv4 communes | 76 544 096 | — |
| Adresses IPv4 exclusives IPverse | 4 085 248 | — |
| Adresses IPv4 exclusives IPdeny | 5 043 696 | — |

![Répartition de la couverture française](docs/figures/france-couverture.png)

Les pourcentages du graphique utilisent **l'union** comme dénominateur. En IPv4, les écarts représentent respectivement 5,07 % de la liste IPverse et 6,18 % de la liste IPdeny si l'on utilise chaque liste comme dénominateur. Ces mesures ne sont pas des taux d'erreur. Les manifestes de cet instantané signalent 1 712 entrées de recouvrement IPv4 entre la France et d'autres pays chez IPverse, deux en IPv6, et aucune chez IPdeny ; il s'agit de CIDR signalés, pas de comptages d'utilisateurs ou de plages nécessairement indépendantes.

**Évaluation des dimensions de qualité :**

- **Intégrité technique :** des contrôles de syntaxe et d'empreinte existent ; ils détectent des altérations, pas des erreurs géographiques à la source.
- **Disponibilité :** des familles sont absentes du jeu IPdeny pour certains pays ; absence ne signifie pas couverture vide. L'inventaire mondial n'est pas prouvé complet.
- **Cohérence :** l'accord entre fournisseurs varie fortement ; les recouvrements entre pays et les divergences françaises justifient un examen ciblé.
- **Fraîcheur :** cet instantané ne mesure pas la stabilité dans le temps. Les deux sources ne sont pas nécessairement produites au même instant ; IPdeny ne fournit pas ici de révision atomique ni de manifeste IPv6.
- **Validité et impact opérationnel : inconnus.** Pour les estimer, constituer un échantillon indépendant d'adresses avec pays et date de référence, stratifié par pays, famille, fournisseur d'accès et cas d'accord/désaccord ; mesurer faux positifs et faux négatifs par source et famille, avec intervalles d'incertitude et pondération selon le trafic réel. Vérifier aussi les plages divergentes et les recouvrements sur des cas représentatifs. Ne pas assimiler une plage plus grande à une source plus fiable.

### Reproduire les graphiques

La collecte, la génération et les tests utilisent la bibliothèque standard. Les graphiques demandent en plus Matplotlib dans l'environnement choisi :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install 'matplotlib>=3.9,<4'
PYTHONPATH=src python -m nginx_country compare > comparaison.json
python scripts/statistics_report.py --input comparaison.json --output docs/figures
```

Le script produit trois PNG et un fichier de statistiques avec l'empreinte de l'entrée. Il attend une comparaison complète incluant la France et ses deux familles comparables. Après une nouvelle exécution, actualiser aussi les chiffres et la date de cette section avant de publier le README.

### Comparaison avec GeoLite — instantané du 20 octobre 2026

L'archive GeoLite du 20 octobre est comparée aux générations IPverse et IPdeny du 23 octobre 2026. L'empreinte SHA-256 et les identifiants de génération figurent dans `data/comparaison-trois.json`. Les dates distinctes peuvent contribuer aux écarts. Les 1 344 blocs IPv4 et 918 blocs IPv6 GeoLite dont le pays estimé n'est pas identifiable ne sont attribués à aucun pays.

| Jaccard médian par pays | IPv4 | IPv6 |
|---|---:|---:|
| IPverse / IPdeny | 90,54 % (240 pays) | 93,72 % (232) |
| IPverse / GeoLite | 89,61 % (249) | 93,49 % (249) |
| IPdeny / GeoLite | 87,49 % (240) | 99,47 % (232) |

Chaque pays a le même poids. Les familles absentes sont exclues de la paire concernée ; la médiane ne mesure ni le trafic ni l'exactitude géographique.

![Distribution des accords par paire et famille](docs/figures/trois-sources-accord.png)

Pour **la France**, l'accord Jaccard vaut respectivement 89,34 %, 91,22 % et 88,22 % en IPv4, et 95,18 %, 95,16 % et 98,67 % en IPv6 pour les trois paires dans l'ordre du tableau. Parmi l'union des plages attribuées à la France par au moins une source, les trois en couvrent ensemble 84,93 % en IPv4 et 94,55 % en IPv6.

![Couverture française des trois sources](docs/figures/trois-sources-france.png)

Les zones exclusives ou attribuées par deux sources représentent des **désaccords d'attribution à la France**, pas des erreurs prouvées. Une majorité de sources ne constitue pas une référence indépendante ; il faut des adresses de localisation connue et représentatives du trafic pour estimer le risque de blocage de visiteurs réellement en France.
