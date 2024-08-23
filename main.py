from prometheus_client import start_http_server, Gauge
import os
import subprocess
import time
import requests

# Gauges pour différentes métriques
disk_usage_gauge = Gauge('ispconfig_disk_usage_bytes', 'Disk usage by site', ['site'])
site_latency_gauge = Gauge('ispconfig_site_latency_seconds', 'Latency of site in seconds', ['site'])
site_status_gauge = Gauge('ispconfig_site_up', 'Site status (1=up, 0=down)', ['site'])
apache_status_gauge = Gauge('ispconfig_apache_up', 'Apache service status (1=up, 0=down)')
mysql_status_gauge = Gauge('ispconfig_mysql_up', 'MySQL service status (1=up, 0=down)')

# Fonction pour récupérer l'utilisation du disque par site web
def get_disk_usage(site_path):
    try:
        # Commande pour obtenir l'utilisation du disque en octets
        usage = subprocess.check_output(['du', '-sb', site_path]).split()[0].decode('utf-8')
        return int(usage)
    except Exception as e:
        return 0

# Fonction pour vérifier l'état d'un service (Apache, MySQL)
def check_service_status(service_name):
    try:
        # Vérifie si le service est actif
        status = subprocess.check_output(['systemctl', 'is-active', service_name]).strip().decode('utf-8')
        return 1 if status == 'active' else 0
    except Exception as e:
        return 0

# Fonction pour vérifier si un site est en ligne et mesurer la latence
def check_site_status(domain):
    try:
        response = requests.get(f"http://{domain}", timeout=5)
        latency = response.elapsed.total_seconds()
        status = 1 if response.status_code == 200 else 0
    except requests.exceptions.RequestException as e:
        latency = float('inf')  # Latence infinie en cas d'échec
        status = 0
    return status, latency

# Fonction pour obtenir tous les sites dans /var/www/clients
def get_sites():
    base_path = "/var/www/clients"
    sites = {}
    for client_dir in os.listdir(base_path):
        client_path = os.path.join(base_path, client_dir)
        if os.path.isdir(client_path):
            for site_dir in os.listdir(client_path):
                if site_dir.startswith("web"):
                    site_path = os.path.join(client_path, site_dir)
                    # Recherche du répertoire SSL
                    ssl_path = os.path.join(site_path, "ssl")
                    domain = None
                    if os.path.exists(ssl_path) and os.listdir(ssl_path):
                        # Recherche du domaine dans les fichiers SSL
                        for file_name in os.listdir(ssl_path):
                            if file_name.endswith('-le.crt'):
                                domain = file_name.split('-le.crt')[0]
                                break
                    # Ajouter le site avec ou sans domaine
                    sites[domain if domain else "Unknown"] = site_path
    return sites

# Fonction principale de collecte des métriques
def collect_metrics():
    sites = get_sites()
    
    for domain, path in sites.items():
        # Mise à jour de l'utilisation du disque
        disk_usage = get_disk_usage(path)
        disk_usage_gauge.labels(site=domain).set(disk_usage)
        
        # Vérification de l'état du site et de sa latence uniquement si le domaine est connu
        if domain != "Unknown":
            status, latency = check_site_status(domain)
            site_status_gauge.labels(site=domain).set(status)
            site_latency_gauge.labels(site=domain).set(latency)

    # Vérifier l'état des services Apache et MySQL
    apache_status = check_service_status('apache2')  # ou 'httpd' selon ta distro
    mysql_status = check_service_status('mysql')  # ou 'mariadb' selon ta config

    # Mettre à jour les métriques des services
    apache_status_gauge.set(apache_status)
    mysql_status_gauge.set(mysql_status)

if __name__ == '__main__':
    # Démarre le serveur HTTP pour exposer les métriques
    start_http_server(8003)
    
    # Boucle de collecte des métriques toutes les 60 secondes
    while True:
        collect_metrics()
        time.sleep(60)
