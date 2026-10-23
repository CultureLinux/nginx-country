# Cadrage des sources et décisions initiales

Recherches documentaires effectuées le 23 octobre 2026. Ce document est un point de départ du lot 0, pas une validation complète des adaptateurs : les archives et les contrôles d'intégration restent à vérifier.

## IPverse

- [geo-ip-blocks](https://github.com/ipverse/geo-ip-blocks) publie des préfixes IPv4 et IPv6 issus d'enregistrements réseau, mis à jour quotidiennement. Ils représentent le pays enregistré, pas nécessairement le lieu réel du trafic.
- Le [JSON français](https://raw.githubusercontent.com/ipverse/geo-ip-blocks/master/country/fr/fr.json) est accessible. Le schéma documenté contient `country`, `countryCode`, `exportMode` et `prefixes.ipv4` / `prefixes.ipv6`, sous forme de listes de CIDR. Le chemin suit `country/<code minuscule>/<code minuscule>.json`.
- Le dépôt indique une licence CC0-1.0. Utiliser ce dépôt et non `country-ip-blocks`.
- À vérifier par intégration : inventaire complet, téléchargement d'une révision cohérente et comportement pour pays ou familles absents ou vides.

## IPdeny

- Les listes agrégées françaises [IPv4](https://www.ipdeny.com/ipblocks/data/aggregated/fr-aggregated.zone) et [IPv6](https://www.ipdeny.com/ipv6/ipaddresses/aggregated/fr-aggregated.zone) sont accessibles et contiennent des CIDR, un par ligne. L'IPv6 agrégé est préférable sous réserve de confirmer la stratégie de collecte.
- La [page de téléchargement](https://www.ipdeny.com/ipblocks/) annonce des archives complètes [IPv4](https://www.ipdeny.com/ipblocks/data/countries/all-zones.tar.gz) et [IPv6](https://www.ipdeny.com/ipv6/ipaddresses/blocks/ipv6-all-zones.tar.gz). Leur contenu, leur intégrité et leur caractère agrégé n'ont pas encore été vérifiés ; ne pas les supposer équivalentes aux listes agrégées.
- Les [limites d'utilisation](https://www.ipdeny.com/usagelimits.php) indiquent au maximum 5 000 téléchargements de zones par jour et par IP, cinq connexions simultanées et suggèrent une attente de 0,5 à 1 seconde entre requêtes. Prévoir une collecte économe et un limiteur par hôte.
- La [notice de copyright](https://www.ipdeny.com/copyright.php) autorise la redistribution des fichiers de zones sous condition de joindre `Copyrights.txt` intact. Les [conditions générales](https://www.ipdeny.com/tos.php) contiennent toutefois une formulation contraire sur la redistribution. Éviter de distribuer des données IPdeny ou fixtures dérivées tant que cette contradiction n'est pas clarifiée ; utiliser des fixtures synthétiques documentaires pour les tests hors ligne.

## Choix de conception proposés

- Collecter chaque fournisseur dans une zone temporaire isolée, puis ne promouvoir que les jeux entièrement validés ; conserver le dernier jeu valide et l'état de chaque tentative séparément.
- Construire un manifeste par source et révision contenant pays, familles, empreintes, provenance et validation. Un inventaire fiable doit être établi avant de considérer `countries: all` comme complet ; une simple réponse HTTP 200 ne suffit pas.
- Pour une première exécution, exiger un inventaire et une validation structurelle complets ; signaler l'absence de référence historique et ne pas prétendre avoir contrôlé les variations. Les pays ou familles légitimement absents doivent être distingués des téléchargements échoués.
- Par défaut, conserver les plages spéciales en les signalant explicitement jusqu'à définition et validation d'une politique d'exclusion précise ; toute exclusion doit être journalisée. Les seuils de variation restent à définir dans la configuration avant publication.
- Comparer les couvertures par source, pays et famille à la dernière release valide, avec des entiers exacts ; signaler les augmentations et diminutions. Une première release n'a pas de référence de variation.
- Séparer les données de travail, les rapports et les releases immuables ; réserver l'écriture du lien actif au processus de déploiement. Construire une configuration candidate dont les includes ciblent explicitement la release candidate, avant toute bascule ; valider aussi la configuration active après bascule.

## Vérifications encore nécessaires

1. Télécharger et inspecter les archives, leurs manifestes et sommes de contrôle ; vérifier leur sécurité d'extraction et déterminer si elles répondent aux besoins agrégés.
2. Tester les schémas et l'inventaire réels des deux fournisseurs, y compris les codes non ISO et familles absentes ; établir les règles de complétude sans confondre absence et échec.
3. Fixer les seuils de variation et la politique des plages spéciales en fonction du contexte d'exploitation.
4. Valider une méthode de configuration candidate sur une installation Nginx représentative, puis la procédure de rollback sur Rocky Linux 9.

## Constat et contrôles de collecte exhaustive

La collecte réelle du 23 octobre 2026 a fourni 253 fichiers IPverse, dont les codes non ISO `AN`, `CS`, `UK`, `YU`, ainsi que 243 zones IPv4 et 235 IPv6 IPdeny, dont les codes non ISO `AP`, `EU`, `ZZ`. Une famille absente de l'inventaire IPdeny est une absence publiée, pas un échec de téléchargement ; elle ne prouve pas une couverture vide. Les fichiers bruts sont conservés, avec une classification pays ISO ou catégorie spéciale dans les nouveaux manifestes. L'instantané ISO utilisé par le programme doit être maintenu lorsque le registre évolue.

La zone IPv4 `AP` était vide. Le fichier `MD5SUM` publié par IPdeny indiquait l'empreinte du fichier vide ; cela confirme les octets publiés, pas l'absence réelle d'adresses. Cette exception est limitée à IPv4/AP et exige la correspondance avec le manifeste. Toutes les autres listes vides restent invalides. Le manifeste IPv4 entier doit correspondre à l'inventaire et chaque fichier à sa somme ; aucun manifeste IPv6 équivalent n'a été trouvé (HTTP 404). Les sommes MD5 du fournisseur servent au contrôle de cohérence, pas à authentifier les données.

Pour IPverse, l'inventaire et les fichiers sont téléchargés à une même révision de commit, et leurs empreintes Git sont vérifiées. Pour chaque source, une disparition par rapport au dernier inventaire retenu bloque la mise à jour. Sans historique, la première collecte est explicitement signalée ; la présence de fichiers dans un inventaire ne garantit pas sa complétude réelle. Les variations de couverture et une éventuelle révision atomique d'IPdeny restent non vérifiées. Les anciennes collectes IPverse, avant fixation de la révision, ne bénéficient pas de ce contrôle.

Vérification locale des données déjà recueillies : les 478 fichiers IPdeny ont passé la validation syntaxique et les 243 fichiers IPv4 correspondent au manifeste récupéré séparément ; les 253 JSON IPverse ont passé la validation syntaxique. Cette vérification rétrospective ne démontre pas une révision cohérente ni la complétude mondiale ; le jeu IPdeny précédent reste non promu.
