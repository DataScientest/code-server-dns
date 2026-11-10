---
name: install-code-server
description: Installe, vérifie et dépanne ce déploiement code-server HTTPS avec Docker Compose, Caddy et DuckDNS, sans exposer les secrets ni perturber les services existants.
---

# Installer et diagnostiquer code-server HTTPS

## Principes
- Lire le `README.md`, `docker-compose.yml`, `Caddyfile` et `.env.example` à la racine du projet avant toute intervention. Adapter les chemins et identifiants à la machine cible.
- Ne jamais demander, afficher ou transmettre le jeton DuckDNS, le mot de passe code-server, les clés privées ou le contenu du `.env`. Faire saisir les secrets en privé ; si un secret a été divulgué, demander sa rotation.
- Ne pas afficher la configuration Compose développée ; utiliser `docker compose config --quiet`. Les journaux Caddy peuvent contenir des informations sensibles : les filtrer ou les relire en privé avant partage.
- Ne pas modifier ou arrêter k3s, Traefik, le code-server de l'hôte ou d'autres services sans demande explicite. Ne pas redémarrer la VM ni supprimer les volumes, `data/`, le dossier de travail ou `.env` sans autorisation.
- L'accès au socket Docker dans code-server confère des privilèges équivalents à root sur l'hôte. Réserver l'accès à des personnes de confiance et signaler les éventuelles expositions HTTP préexistantes.

## Préparation
1. Vérifier Docker et le plugin Compose, l'accès au socket, les identifiants UID/GID et l'espace de travail. Vérifier que le port TCP 444 est disponible et autorisé par le réseau ; Docker peut contourner certaines règles de pare-feu locales.
2. Demander à l'utilisateur de créer un sous-domaine DuckDNS et de renseigner son nom complet ainsi que son jeton dans `.env` depuis une session privée. Créer `.env` depuis `.env.example` sans écraser un fichier existant et limiter ses permissions à `600`.
3. Vérifier que `WORKSPACE`, `data/` et `CODE_SERVER_CONFIG` existent et sont accessibles avec les UID/GID configurés. Le fichier code-server doit contenir une authentification par mot de passe robuste ; ne pas afficher son contenu.
4. Ne pas supposer que l'IPv4 publique sortante et l'IPv4 entrante de la VM sont identiques. Le service de mise à jour ne gère pas les enregistrements IPv6.

## Démarrage et vérification
Depuis la racine du projet, valider avec `docker compose config --quiet`, puis démarrer avec `docker compose up -d --build` si l'utilisateur a demandé l'installation. Contrôler les conteneurs avec `docker compose ps` et la mise à jour avec `docker compose logs --tail=20 duckdns`.

La requête HTTPS doit utiliser le nom DuckDNS et le port 444. Vérifier la chaîne et le nom du certificat, puis demander un test depuis le navigateur et le réseau cible : connexion, terminal et WebSockets. Les tests depuis la VM ne prouvent pas l'accès depuis Internet ou un proxy d'entreprise. Comparer l'IPv4 DNS à l'IPv4 publique entrante indiquée par le fournisseur.

`scripts/duckdns_updater.py` actualise uniquement l'IPv4 au démarrage et environ toutes les cinq minutes ; il n'envoie ni `txt` ni `clear`. `Caddyfile` utilise un résolveur public pour vérifier la propagation du défi DNS. Ne pas conclure qu'un renouvellement ou un redémarrage de VM fonctionne sans l'avoir testé.

## Dépannage et tests
- Si DuckDNS refuse la mise à jour, vérifier en privé le domaine, le jeton, la connexion sortante et les journaux filtrés. Un message d'acceptation ne garantit pas que l'IP détectée est celle accessible en entrée.
- Si le certificat échoue, examiner les erreurs Caddy sans révéler de jeton, la propagation TXT et l'accès DNS sortant ; éviter les tentatives répétées inutiles contre les autorités de certification.
- Si le navigateur n'accède pas au service, vérifier le port 444, le pare-feu cloud, le DNS et les restrictions du réseau. Pour un éditeur bloqué, vérifier les WebSockets et les journaux.
- Pour les tests unitaires sans requête DuckDNS, lancer `python3 -m unittest discover -s tests -v` depuis la racine. Utiliser des valeurs fictives et des simulations, jamais des requêtes DNS publiques de test.
- Si la configuration `.env` change, recréer les conteneurs concernés avec `docker compose up -d` ; un simple redémarrage ne recharge pas nécessairement les variables Compose.

## Fin d'intervention
Mettre à jour la documentation si le comportement change. Rapporter ce qui a été réellement vérifié et ce qui reste à tester. Avant une publication, vérifier que `.env`, `data/`, les clés, les journaux et toute donnée privée sont exclus ; ne jamais publier de secrets.