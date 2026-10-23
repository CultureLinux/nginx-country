# nginx-country

Outil Python en préparation pour récupérer et comparer les listes IP par pays d'IPverse et d'IPdeny, puis générer des règles Nginx. Une collecte expérimentale de tous les pays ou par pays est disponible ; la commande `nginx-country`, la comparaison et le déploiement ne sont pas encore implémentés.

## Prérequis

- Python 3 avec le module `venv` et `pip` ; l'environnement actuel a été créé avec Python 3.9.25.
- Un accès HTTPS aux fournisseurs sera nécessaire pour les futures vérifications réseau.

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

## Collecter tous les pays

Depuis la racine du projet :

```bash
PYTHONPATH=src python3 -m nginx_country
```

La commande parcourt les inventaires publiés par chaque source, télécharge les fichiers et conserve les données brutes dans `data/raw/ipverse/all/` et `data/raw/ipdeny/all/`. Les sources sont traitées indépendamment ; un échec renvoie un code non nul et conserve le lien vers la précédente collecte de cette source. La collecte IPdeny attend une seconde entre les téléchargements et peut prendre plusieurs minutes. Les fichiers partiels restent dans un répertoire de travail daté par identifiant.

Les inventaires peuvent contenir des codes non ISO. Leur complétude et la cohérence des révisions ne sont pas garanties : ces données sont expérimentales et ne doivent pas être déployées en production sans contrôles supplémentaires.

## Collecter un pays

Après activation du venv, depuis la racine :

```bash
PYTHONPATH=src python -m nginx_country FR
```

Remplacer `FR` par le code à deux lettres voulu. Les réponses et leurs métadonnées sont stockées dans `data/raw/`, ignoré par Git ; `--output CHEMIN` permet de choisir un autre répertoire. Les deux sources sont traitées indépendamment et une erreur renvoie un code de sortie non nul. Chaque collecte réussie crée un répertoire daté par ses métadonnées et met à jour un lien vers cette version ; une collecte échouée conserve la précédente.

Cette commande vérifie la syntaxe et la famille des CIDR, mais ne garantit pas la complétude des données reçues ni la validité ISO du code ; elle ne constitue pas un jeu prêt pour la production. Les listes IPdeny vides sont rejetées, y compris lorsqu'une famille pourrait légitimement être absente. La CLI définitive reste à développer.

Exécuter les tests hors ligne :

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Documentation du projet

- [Cahier des charges](nginx-country-cahier-des-charges.md) : objectifs et exigences.
- [Découpage en lots](AGENT.md) : étapes, dépendances et critères de validation.
- [Cadrage des sources](docs/cadrage-sources.md) : recherches effectuées et points à vérifier.

Le déploiement automatique est prévu désactivé par défaut ; aucune activation sur un serveur réel ne doit être effectuée sans validation explicite. Les données par pays ne garantissent pas la localisation réelle des utilisateurs et leur utilisation peut bloquer des utilisateurs légitimes.
