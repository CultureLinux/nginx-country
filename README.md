# nginx-country

Outil Python en préparation pour récupérer et comparer les listes IP par pays d'IPverse et d'IPdeny, puis générer des règles Nginx. Une collecte expérimentale de tous les pays ou par pays est disponible ; la commande `nginx-country`, la comparaison et le déploiement ne sont pas encore implémentés.

## Flux de traitement

Le projet prévoit deux flux indépendants, un par fournisseur :

```text
IPverse ─┐
         ├─> collecte et contrôles ─> données brutes par source
IPdeny ──┘                              │
                                       ├─> normalisation des CIDR          [à développer]
                                       ├─> génération des règles Nginx    [à développer]
                                       ├─> comparaison et rapports        [à développer]
                                       └─> validation et déploiement      [à développer]
```

Aujourd'hui, seule la collecte expérimentale est disponible. Elle télécharge les données de chaque source, vérifie leur structure et conserve les fichiers et leurs métadonnées. Une collecte complète réussie met à jour un lien par source ; en cas d'erreur, le lien précédent est conservé et l'autre source reste traitée. Ces liens désignent les données collectées : ils n'activent aucune configuration Nginx.

La normalisation regroupera et triera les plages par pays et famille IP. La génération produira ensuite des fichiers `XX-allow.conf` et `XX-deny.conf` séparés par fournisseur. La comparaison permettra d'examiner les écarts avant de choisir explicitement une source. Enfin, la validation et le déploiement prévus devront tester la configuration Nginx et permettre un retour arrière ; le déploiement automatique restera désactivé par défaut.

## Prérequis

- Python 3 avec le module `venv` et `pip` ; l'environnement actuel a été créé avec Python 3.9.25.
- Un accès HTTPS à GitHub et à IPdeny est nécessaire pour la collecte ; les tests unitaires fonctionnent hors ligne.

Sur Rocky Linux 9, installer Python si nécessaire :

```bash
sudo dnf install python3
```

## Préparer l'environnement de développement

Depuis la racine du projet :

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python --version
python -m pip --version
```

L'environnement `.venv/` est local au projet et ignoré par Git. L'activation s'applique au terminal courant ; pour un nouveau terminal, reprendre uniquement la commande `source .venv/bin/activate` depuis la racine du projet. Pour le quitter :

```bash
deactivate
```

Il n'y a pas encore de dépendances externes ni de paquet à installer.

## Commandes de récupération

### Tous les pays

Depuis la racine du projet :

```bash
PYTHONPATH=src python3 -m nginx_country
```

La commande parcourt les inventaires publiés par chaque source, télécharge les fichiers et conserve les données brutes dans `data/raw/ipverse/all/` et `data/raw/ipdeny/all/`. Les sources sont traitées indépendamment ; un échec renvoie un code non nul et conserve le lien vers la précédente collecte de cette source. La collecte IPdeny attend une seconde entre les téléchargements et peut prendre plusieurs minutes. Les fichiers partiels restent dans un répertoire de travail daté par identifiant.

Les métadonnées distinguent les pays ISO des codes spéciaux. IPverse utilise une révision Git fixe et vérifie chaque empreinte Git ; IPdeny vérifie les empreintes MD5 de son manifeste IPv4. Une liste IPv4 `AP` vide est conservée uniquement si ce manifeste confirme son empreinte ; les autres listes vides sont rejetées. Les fichiers de la collecte précédente ne doivent pas disparaître. La première collecte ne dispose pas de référence historique, et IPdeny ne fournit pas ici de manifeste IPv6 ni de révision cohérente entre ses fichiers. Les contrôles de variation de couverture restent à faire : ces données ne sont pas prêtes pour un déploiement en production.

### Un seul pays

Après activation du venv, depuis la racine :

```bash
PYTHONPATH=src python -m nginx_country FR
```

Remplacer `FR` par le code à deux lettres voulu. Les réponses et leurs métadonnées sont stockées dans `data/raw/`, ignoré par Git ; `--output CHEMIN` permet de choisir un autre répertoire. Les deux sources sont traitées indépendamment et une erreur renvoie un code de sortie non nul. Chaque collecte réussie crée un répertoire daté par ses métadonnées et met à jour un lien vers cette version ; une collecte échouée conserve la précédente.

La commande par pays vérifie la syntaxe et la famille des CIDR, mais ne garantit pas la complétude des données reçues ni la validité ISO du code ; elle ne constitue pas un jeu prêt pour la production. Les listes IPdeny vides sont rejetées, y compris lorsqu'une famille pourrait légitimement être absente. La CLI définitive reste à développer.

### Répertoire de sortie et résultat

Pour enregistrer une collecte complète ailleurs que dans `data/raw/` :

```bash
PYTHONPATH=src python3 -m nginx_country --output /chemin/vers/donnees
```

La même option fonctionne pour un pays :

```bash
PYTHONPATH=src python3 -m nginx_country FR --output /chemin/vers/donnees
```

La commande affiche un résultat pour chaque fournisseur à la fin. Elle renvoie `0` si les deux collectes réussissent et `1` si au moins une échoue. Une erreur d'arguments renvoie `2`. Pour afficher les options disponibles :

```bash
PYTHONPATH=src python3 -m nginx_country --help
```

Dans le répertoire de sortie, `ipverse/all` et `ipdeny/all` sont des liens vers les dernières collectes complètes retenues. Les collectes par pays utilisent des liens tels que `ipverse/FR` et `ipdeny/FR`. Chaque répertoire de collecte contient les fichiers bruts et un `metadata.json` avec leur provenance et leurs empreintes. Une tentative incomplète peut laisser des fichiers dans un répertoire `all-<identifiant>` sans mettre à jour le lien `all`.

## Commandes de test

Depuis la racine du projet, exécuter toute la suite de tests unitaires hors ligne :

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Ces tests utilisent des données synthétiques et des réponses réseau simulées. Ils vérifient notamment la validation des données, l'indépendance des sources, le traitement d'une zone vide et les contrôles d'inventaire. Ils ne téléchargent pas les données des fournisseurs et ne valident pas une configuration Nginx. Pour vérifier l'accès réel aux fournisseurs, lancer une commande de récupération ci-dessus ; elle écrit les données dans le répertoire de sortie.

## Documentation du projet

- [Cahier des charges](nginx-country-cahier-des-charges.md) : objectifs et exigences.
- [Découpage en lots](AGENT.md) : étapes, dépendances et critères de validation.
- [Cadrage des sources](docs/cadrage-sources.md) : recherches effectuées et points à vérifier.

Le déploiement automatique est prévu désactivé par défaut ; aucune activation sur un serveur réel ne doit être effectuée sans validation explicite. Les données par pays ne garantissent pas la localisation réelle des utilisateurs et leur utilisation peut bloquer des utilisateurs légitimes.
