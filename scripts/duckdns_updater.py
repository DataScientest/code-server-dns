"""Actualise l'IPv4 DuckDNS sans modifier les paramètres de validation TXT."""

import http.client
import os
import re
import socket
import time
from urllib.parse import urlencode

HOST = "www.duckdns.org"
INTERVAL = 300
TIMEOUT = 20
DOMAIN_PATTERN = re.compile(r"([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)\.duckdns\.org\Z")


def subdomain(domain):
    match = DOMAIN_PATTERN.fullmatch(domain.lower())
    if not match:
        raise ValueError("DOMAIN doit être un sous-domaine DuckDNS complet.")
    return match.group(1)


def connect_ipv4(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    host, port = address
    last_error = None
    for _, _, _, _, sockaddr in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM):
        try:
            return socket.create_connection((sockaddr[0], port), timeout, source_address)
        except OSError as error:
            last_error = error
    raise last_error or OSError("Aucune adresse IPv4 disponible")


def update(domain, token, connection_factory=http.client.HTTPSConnection):
    name = subdomain(domain)
    if not token:
        raise ValueError("DUCKDNS_TOKEN doit être renseigné.")
    query = urlencode({"domains": name, "token": token, "ip": ""})
    connection = connection_factory(HOST, timeout=TIMEOUT)
    connection._create_connection = connect_ipv4
    try:
        connection.request("GET", "/update?" + query)
        response = connection.getresponse()
        return response.status == 200 and response.read(1024).strip() == b"OK"
    finally:
        connection.close()


def main():
    while True:
        try:
            success = update(os.environ.get("DOMAIN", ""), os.environ.get("DUCKDNS_TOKEN", ""))
            if success:
                print("DuckDNS : mise à jour IPv4 acceptée.", flush=True)
            else:
                print("DuckDNS : mise à jour refusée ou réponse inattendue ; nouvel essai dans 5 minutes.", flush=True)
        except (OSError, ValueError, http.client.HTTPException):
            # Les détails réseau peuvent contenir l'URL et donc le jeton.
            print("DuckDNS : configuration ou connexion incorrecte ; nouvel essai dans 5 minutes.", flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()