# code-server en HTTPS avec Docker et DuckDNS

Ce dossier contient une installation indépendante de code-server, Caddy et un service de mise à jour DuckDNS. Elle sert code-server en HTTPS sur le port **444** de la VM. Caddy obtient et renouvelle un certificat Let's Encrypt pour un nom DuckDNS grâce à une validation DNS : aucun port 80 ou 443 de la VM n'est nécessaire pour ce certificat. Le déploiement ne modifie pas k3s ou son Traefik.

**État des tests sur cette VM :** les images ont été construites et la configuration Caddy validée. DuckDNS a accepté la mise à jour IPv4 et Caddy a obtenu un certificat Let's Encrypt pour le domaine configuré. La page de connexion HTTPS répond avec un certificat valide depuis la VM, y compris via le nom public. Les commandes Docker et Docker Compose et l'écriture dans les dossiers montés ont été vérifiées dans un test local précédent. Le service de mise à jour DNS a aussi été testé avec des réponses simulées dans un conteneur sans réseau. Le redémarrage de la VM, le renouvellement réel du certificat, la connexion avec le mot de passe, les WebSockets et l'accès depuis un réseau extérieur ou d'entreprise restent à tester.

## Avant de commencer

- Une VM Linux disposant de Docker et du plugin Docker Compose. L'utilisateur doit avoir accès au socket Docker.
- Une IP publique accessible et la possibilité d'autoriser le port TCP 444 entrant dans les règles réseau de la VM et du fournisseur cloud. Vérifier que le port n'est pas déjà utilisé ; l'utilisation de Docker peut contourner certaines règles de pare-feu locales comme UFW.
- Un compte [DuckDNS](https://www.duckdns.org/), un sous-domaine et son jeton. Ce jeton donne accès à la gestion DNS associée au compte : le garder secret et ne pas le partager avec les stagiaires.
- Un accès Internet sortant depuis la VM vers DuckDNS, Let's Encrypt et les registres nécessaires à la construction des images.
- Un navigateur capable d'accéder au domaine et au port 444, et un réseau qui autorise les WebSockets. HTTPS ne garantit pas le passage d'un proxy d'entreprise : certains bloquent le port, le domaine ou les WebSockets.

Le certificat protège **le nom de domaine**, pas une URL contenant directement l'adresse IP. Un changement d'IP ne nécessite pas un nouveau certificat : le service `duckdns` demande la mise à jour de l'IPv4 au démarrage, puis toutes les cinq minutes environ, y compris après un échec.

## Organisation du projet

- `docker-compose.yml` et `Caddyfile` : services et configuration HTTPS.
- `scripts/duckdns_updater.py` : actualisation automatique de l'IPv4 DuckDNS.
- `tests/` : tests unitaires sans appel DNS réel.
- `.agents/skills/install-code-server/SKILL.md` : instructions d'installation et de diagnostic pour un agent.
- `.env.example` : modèle de configuration ; `.env` et `data/` sont locaux et ne doivent pas être publiés.

## 1. Préparer le domaine

1. Connectez-vous sur [DuckDNS](https://www.duckdns.org/) et créez un sous-domaine, par exemple `formation.duckdns.org`.
2. L'adresse IPv4 initiale visible par DuckDNS depuis votre poste n'est pas nécessairement celle de la VM. Après démarrage, le service `duckdns` demandera automatiquement son remplacement par l'IPv4 détectée depuis la VM.
3. Conservez le jeton affiché par DuckDNS : vous le saisirez dans le fichier privé `.env` de la VM. Ne le collez pas dans une conversation ou une commande partagée.

## 2. Préparer les dossiers et le mot de passe

Dans le terminal de la VM, placez-vous dans ce dossier et créez les dossiers de travail et de données :

```bash
cd ~/code-server-dns
mkdir -p ~/work data
```

Par défaut, le conteneur utilise `~/work` et lit la configuration existante `~/.config/code-server/config.yaml` en lecture seule. Le mot de passe est celui défini dans ce fichier ; les deux installations partagent donc ce mot de passe. Consultez-le en privé si nécessaire, sans le publier.

Sur une VM qui ne possède pas encore ce fichier, créez le dossier `~/.config/code-server`, puis créez `config.yaml` avec un éditeur. Exemple à adapter avec un mot de passe long et unique :

```yaml
bind-addr: 127.0.0.1:8080
auth: password
password: "REMPLACER_PAR_UN_MOT_DE_PASSE_FORT"
cert: false
```

Protégez ce fichier :

```bash
chmod 600 ~/.config/code-server/config.yaml
```

Le démarrage du conteneur utilise explicitement `0.0.0.0:8080` **dans son réseau Docker privé** ; ce port n'est pas publié sur la VM par ce Compose. L'éditeur le rend accessible uniquement par le proxy HTTPS Caddy.

Pour monter un autre dossier, choisissez son chemin absolu dans `.env` à l'étape suivante. Il doit exister et être accessible en écriture par l'utilisateur configuré. Seul ce dossier est monté comme espace de travail ; le terminal de code-server tourne dans le conteneur, pas directement dans le système hôte.

## 3. Configurer le déploiement

Créez le fichier privé à partir de l'exemple et ouvrez-le avec un éditeur :

```bash
cd ~/code-server-dns
umask 077
cp -n .env.example .env
chmod 600 .env
nano .env
```

`cp -n` conserve un éventuel fichier `.env` existant. Renseignez :

- `DOMAIN` : le nom complet, par exemple `formation.duckdns.org`.
- `DUCKDNS_TOKEN` : le jeton personnel DuckDNS. Ne laissez pas la valeur d'exemple.
- `DOCKER_GID` : le numéro du groupe propriétaire du socket Docker. Pour le connaître, exécutez `stat -c '%g' /var/run/docker.sock`. Sur la VM testée, c'est `988` ; cette valeur peut être différente ailleurs.
- `HOST_UID` et `HOST_GID` : les identifiants numériques de l'utilisateur propriétaire des dossiers. Vérifiez-les avec `id -u` et `id -g` ; ils valent `1000` sur la VM testée.
- `WORKSPACE` : le chemin absolu du dossier à ouvrir, par exemple `/home/ubuntu/work`.
- `CODE_SERVER_CONFIG` : le chemin absolu du fichier de configuration avec le mot de passe.

Dans nano, enregistrez avec `Ctrl+O`, puis Entrée, et quittez avec `Ctrl+X`. Ne versionnez pas `.env` et ne partagez pas les sorties qui contiendraient son contenu. Le jeton est également accessible aux personnes qui administrent Docker sur la VM. `.gitignore` exclut `.env`, ses variantes et `data/` ; `.dockerignore` exclut les fichiers locaux du contexte de construction.

## 4. Démarrer

Dans `~/code-server-dns` :

```bash
docker compose config --quiet
docker compose up -d --build
```

La première construction télécharge les images et compile une image Caddy avec le module DuckDNS. Le module DuckDNS est téléchargé lors de la construction ; sa version n'est pas figée. L'image testée contenait la version `v0.5.0`. Le service de mise à jour utilise l'image `python:3.13-alpine`, dont le tag peut évoluer. Les données code-server sont conservées dans `data/` et les certificats dans des volumes Docker nommés.

Vérifiez le démarrage :

```bash
docker compose ps
docker compose logs --tail=100 caddy
docker compose logs --tail=20 duckdns
```

La première obtention du certificat peut prendre un moment, notamment à cause de la propagation DNS. Évitez de partager les journaux sans les relire : ils peuvent contenir des informations d'infrastructure ou des secrets. Ne lancez pas `docker compose config` sans `--quiet` dans une sortie partagée, car la configuration développée peut contenir le jeton. Après une modification de `.env`, exécutez `docker compose up -d` pour recréer les services concernés avec les nouvelles valeurs.

Le journal `duckdns` indique si DuckDNS a accepté ou refusé la demande ; l'acceptation ne prouve pas que l'adresse détectée est accessible depuis Internet. Le service n'affiche pas le jeton, mais il est transmis à DuckDNS dans une requête HTTPS et reste accessible aux administrateurs Docker. Ne partagez pas de traces réseau ou de configuration contenant la requête.

## 5. Ouvrir code-server

Depuis un navigateur autorisé, ouvrez :

```text
https://formation.duckdns.org:444
```

Remplacez le nom par le vôtre et utilisez le mot de passe du fichier de configuration. Vérifiez que le navigateur reconnaît le certificat, puis ouvrez un fichier, un terminal et testez les fonctions nécessaires au cours. Dans le terminal intégré, vous pouvez par exemple vérifier `docker version` et `docker compose version`.

**Attention :** le socket Docker du système hôte est monté dans code-server. Toute personne ayant accès au terminal peut contrôler Docker et obtenir des privilèges équivalents à root sur la VM. Les conteneurs lancés depuis ce terminal tournent sur l'hôte ; leurs chemins de montage se rapportent à l'hôte, pas au système de fichiers du conteneur code-server. Réservez cet accès à des utilisateurs de confiance et utilisez un mot de passe fort.

## 6. Vérifier le renouvellement et diagnostiquer

Caddy renouvelle le certificat automatiquement tant que les conteneurs fonctionnent, que les volumes Caddy persistent, que le jeton reste valide et que le DNS et Let's Encrypt sont accessibles. Vérifiez les journaux après l'émission et lors d'un renouvellement ; un redémarrage ne prouve pas que ce dernier fonctionne.

Pour la vérification de propagation DNS, `Caddyfile` utilise le résolveur public Cloudflare `*******` avec un délai maximal de cinq minutes. Ce réglage concerne les requêtes DNS de validation : il ne fait pas transiter l'accès à code-server par Cloudflare. Il a été ajouté parce que les vérifications directes vers les serveurs DNS DuckDNS expiraient depuis cette VM. L'accès sortant au résolveur reste nécessaire pour obtenir et renouveler les certificats.

### Changement d'IP ou redémarrage de la VM

Le conteneur `duckdns` utilise `DOMAIN` et `DUCKDNS_TOKEN` de `.env` ; aucune autre configuration n'est nécessaire. Il contacte DuckDNS directement en HTTPS par IPv4 et lui laisse détecter l'adresse source. Il ne transmet aucun paramètre `txt` ou `clear`, afin de ne pas demander la modification du TXT utilisé par Caddy. La compatibilité effective pendant une validation ACME reste à vérifier avec un compte réel.

Les conteneurs utilisent `restart: unless-stopped` et Docker était activé au démarrage sur cette VM. **Avant d'arrêter la VM, laissez les conteneurs fonctionner : ne lancez pas `docker compose stop` ou `docker compose down` si vous voulez qu'ils redémarrent automatiquement.** Arrêtez la VM normalement sans la supprimer et vérifiez que son disque est conservé.

Les conteneurs redémarrent lorsque Docker démarre, sauf s'ils ont été explicitement arrêtés ; après `docker compose stop`, utilisez `docker compose start`. Après `docker compose down`, recréez-les avec `docker compose up -d`. L'actualisation reprend au démarrage du conteneur. Une panne réseau ou un refus provoque un nouvel essai après cinq minutes environ. Une mise à jour réussie peut encore être suivie d'un délai de propagation ou de cache DNS.

Vérifiez `docker compose logs --tail=20 duckdns`, puis comparez l'adresse IPv4 renvoyée par `dig +short A formation.duckdns.org` à l'IP publique **entrante** affichée par votre fournisseur cloud, en remplaçant le nom par le vôtre. Si `dig` n'est pas installé, utilisez `getent ahostsv4 formation.duckdns.org`. Après un redémarrage de la VM, effectuez de nouveau ces vérifications et testez l'URL HTTPS depuis un réseau externe.

Cette détection suppose que l'IPv4 de sortie est aussi l'adresse publique entrante de la VM. Avec un NAT ou une passerelle de sortie distincte, elle peut inscrire une mauvaise adresse : il faut alors adapter la détection à votre fournisseur. Le service ne gère pas l'IPv6 ; vérifiez qu'aucun enregistrement AAAA obsolète ne dirige les navigateurs vers une mauvaise adresse. Le port TCP 444 doit rester autorisé après le redémarrage.

- **Le navigateur ne se connecte pas :** vérifiez l'IP renseignée chez DuckDNS, les journaux `duckdns`, l'ouverture du port TCP 444 dans le cloud et le pare-feu, puis testez depuis un autre réseau autorisé. Un proxy d'entreprise peut refuser ce port ou ce domaine.
- **Erreur de certificat :** utilisez bien le nom DuckDNS, pas l'IP ; vérifiez le jeton, le nom de domaine et les journaux Caddy. Attendez la propagation DNS et assurez-vous que la VM peut joindre les services nécessaires.
- **Page ouverte mais éditeur ou terminal bloqué :** vérifiez l'autorisation des WebSockets sur le proxy et le navigateur, ainsi que les journaux des conteneurs.
- **Erreur de permission :** vérifiez `HOST_UID`, `HOST_GID`, `DOCKER_GID`, les permissions du fichier de configuration, de `data/` et du dossier `WORKSPACE`.
- **Échec de construction Caddy :** vérifiez l'accès aux registres Docker et aux dépendances Go ; le module DuckDNS doit être compilé dans l'image.

Si DuckDNS n'est pas adapté, il faut choisir un fournisseur DNS disposant d'une API et remplacer le module et la configuration Caddy : le jeton DuckDNS ne fonctionne pas avec les autres fournisseurs.

Pour relancer les tests locaux de l'actualisation DNS, sans accès à DuckDNS : `python3 -m unittest discover -s tests -v` depuis ce dossier. Ces simulations vérifient notamment les paramètres envoyés, les réponses `OK`/`KO`, les erreurs et les tentatives successives ; elles ne prouvent pas le comportement du service DuckDNS réel.

## 7. Arrêter ou retirer

Dans `~/code-server-dns` :

```bash
docker compose stop
```

Pour redémarrer : `docker compose start`. Pour retirer les conteneurs et le réseau de ce projet sans supprimer les volumes de certificats, le dossier `data/` ou le dossier de travail :

```bash
docker compose down
```

Les certificats, `data/`, le dossier de travail et `.env` persistent. Leur suppression est une opération séparée et définitive : ne les supprimez qu'après avoir vérifié qu'ils ne contiennent rien à conserver. Le compte et le sous-domaine DuckDNS doivent être supprimés ou révoqués séparément si vous ne les utilisez plus.

## Accès HTTP existant sur cette VM

Le service code-server déjà installé sur la VM reste actif et exposé en HTTP sur le port 8080. Cette installation HTTPS ne ferme pas cet accès ; sa suppression ou sa restriction nécessite une décision et une vérification séparées pour ne pas perturber les cours.
