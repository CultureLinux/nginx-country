# Plan : normalisation des adresses et génération Nginx

**Objectif :** à partir des collectes retenues, produire pour chaque fournisseur et chaque pays ISO des fichiers Nginx cohérents et reproductibles, sans activation.

**Architecture :** un lecteur contrôle les métadonnées et les empreintes, puis traduit les deux formats en un modèle commun. Un normaliseur traite séparément IPv4 et IPv6 ; un générateur écrit les fichiers et un manifeste par source dans une nouvelle version de travail.

**Technologie :** Python 3.9+, bibliothèque standard `ipaddress`, tests `unittest` hors ligne. **Référence :** `nginx-country-cahier-des-charges.md`, sections 3 à 7, et `AGENT.md`, lot 2.

## Contraintes et points de vigilance

- Préserver la commande actuelle de collecte et ses données ; aucune modification de Nginx ni aucun rechargement.
- Utiliser uniquement les collectes complètes retenues `data/raw/<source>/all`, après vérification du manifeste et des empreintes SHA-256 ; refuser un manifeste d'échec ou incomplet. Les anciennes collectes sans les nouveaux champs doivent être explicitement signalées et refusées pour la génération, avec instruction de relancer la collecte ; ne pas leur attribuer rétroactivement une révision ou un état de validation.
- La collecte complète IPdeny antérieure n'a pas été promue ; une nouvelle collecte réussie est nécessaire pour cette source. Une source absente ne doit pas empêcher la génération de l'autre.
- Les pays sont ceux de l'instantané ISO du projet. Conserver les codes spéciaux dans les données brutes et les signaler ; ne pas générer de fichier pays pour eux.
- Une famille absente doit être distinguée d'une famille présente et vide, et d'un fichier manquant. Ne pas inventer une couverture vide quand la source ne publie pas de famille.
- Préserver et signaler les plages spéciales par défaut ; aucune exclusion silencieuse. Leur classification et leur éventuelle exclusion doivent reposer sur une politique explicite et configurable, documentée et testée.
- Les fichiers `allow` et `deny` d'un pays doivent contenir les mêmes CIDR et ne jamais inclure `deny all`. Les CIDR documentaires sont réservés aux tests.
- Aucun test réseau, Nginx, systemd ni serveur réel dans la suite unitaire ; les vérifications d'intégration sont séparées.
- Le statut expérimental et les limites de complétude et de cohérence IPdeny restent visibles. La génération n'autorise pas un déploiement.

## 1. Lire et contrôler les jeux collectés

**Fichiers :** créer `src/nginx_country/datasets.py` et `tests/test_datasets.py`.

- [ ] Définir un modèle interne par source et code pays : listes de préfixes IPv4 et IPv6, état de chaque famille (`present`, `empty`, `absent`), provenance et empreintes.
- [ ] Écrire d'abord les tests pour un JSON IPverse et deux zones IPdeny synthétiques : pays et familles interprétés correctement, absence d'une famille IPdeny distinguée d'une liste vide.
- [ ] Tester le rejet d'une empreinte SHA-256 incorrecte, d'un fichier manquant, d'un chemin de manifeste sortant du répertoire et d'un manifeste ancien ou contenant des erreurs ; conserver la possibilité de traiter l'autre source.
- [ ] Implémenter `load_dataset(root, source)` à partir du lien `all` retenu ; vérifier source, état, chemins, fichiers et empreintes avant lecture. Rejeter explicitement les métadonnées anciennes qui ne prouvent pas les contrôles requis.
- [ ] Tester que `AP`, `EU` et les autres codes hors ISO sont signalés mais exclus des pays à générer.
- [ ] Exécuter `PYTHONPATH=src python3 -m unittest discover -s tests -v`.

## 2. Normaliser les réseaux et signaler les anomalies

**Fichiers :** créer `src/nginx_country/normalize.py` et `tests/test_normalize.py`.

- [ ] Écrire les tests : CIDR mal formé ou mauvaise famille rejeté ; `192.0.2.7/24` devient `192.0.2.0/24` ; doublons et réseaux inclus supprimés ; `192.0.2.0/25` et `192.0.2.128/25` deviennent `192.0.2.0/24` ; équivalents IPv6 et ordre stable vérifiés.
- [ ] Implémenter `normalize_cidrs(prefixes, family)` avec `ipaddress.ip_network(..., strict=False)` et `collapse_addresses`, sans parcourir les adresses ; trier par adresse puis longueur de préfixe.
- [ ] Définir et documenter une liste versionnée et explicite de réseaux spéciaux et une politique configurable `keep` ou `exclude`. Par défaut `keep` : signaler les intersections sans modifier les données. En mode `exclude`, soustraire exactement les intersections, y compris pour les préfixes partiellement recouvrants, et journaliser chaque exclusion ; ne pas s'appuyer implicitement sur les classifications variables selon la version de Python.
- [ ] Tester les intersections totales et partielles, en IPv4 et IPv6, la préservation par défaut et l'exclusion configurable sans perte des adresses restantes.
- [ ] Détecter les recouvrements entre pays d'une même source et famille, les rapporter sans réattribuer les plages ; tester chevauchement, contiguïté sans chevauchement et sources différentes.
- [ ] Exécuter la suite complète hors ligne.

## 3. Générer les fichiers Nginx

**Fichiers :** créer `src/nginx_country/generate.py` et `tests/test_generate.py`.

- [ ] Écrire les tests pour deux pays et deux sources : `FR-allow.conf` et `FR-deny.conf` présentent exactement les mêmes réseaux IPv4 et IPv6 ; chaque ligne utilise la bonne directive ; aucun `deny all`.
- [ ] Générer sous `generated/<source>/<version>/` et créer un manifeste comprenant source, révision si connue, empreintes des entrées, familles absentes, codes spéciaux ignorés, plages spéciales et recouvrements. Inclure dans les fichiers un en-tête source, pays, familles, date et identifiant de génération.
- [ ] Séparer métadonnées temporelles et contenu effectif : tester que des entrées et options identiques produisent les mêmes règles et empreintes de contenu, même à des dates différentes.
- [ ] Écrire la version dans un répertoire temporaire sur le même système de fichiers ; ne rendre la version visible qu'après génération complète. Une erreur conserve les résultats précédents et ne mélange pas les sources.
- [ ] Tester pays sans famille disponible, fichier corrompu, erreur d'écriture et indépendance des sources ; aucune génération ne doit transformer une famille absente en preuve de couverture vide.
- [ ] Exécuter la suite complète hors ligne.

## 4. Commande et documentation

**Fichiers :** modifier `src/nginx_country/__main__.py`, `README.md` ; créer `tests/test_cli_generate.py`.

- [ ] Ajouter `PYTHONPATH=src python3 -m nginx_country generate` avec `--input data/raw`, `--output generated` et `--dry-run` ; conserver la syntaxe existante de collecte, dont `FR`, `all` et `--output`.
- [ ] Tester la commande avec des données synthétiques : génération des deux sources, une source absente, erreur d'entrée, code de sortie non nul si une source échoue, et `--dry-run` sans écriture.
- [ ] Documenter les commandes de collecte, génération et tests, l'arborescence des résultats, les états de famille, les avertissements et les limites ; préciser que la génération n'active rien.
- [ ] Exécuter la suite complète et vérifier l'aide CLI. Prévoir séparément un essai manuel avec des données réelles fraîchement collectées ; documenter si une source reste indisponible.

## Critères de fin

La suite hors ligne passe ; les deux formats sont contrôlés avant lecture ; les résultats sont déterministes et séparés par source ; toutes les anomalies sont visibles ; une erreur préserve les versions précédentes. Le test avec de vraies données ne remplace pas les tests unitaires et ses résultats sont consignés distinctement. La comparaison, la publication et le déploiement restent des lots ultérieurs.
