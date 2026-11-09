# Log Analyser

J’ai fait ce projet pour analyser des connexions SSH à partir de fichiers de
journaux. Le programme lit les fichiers `.log` et `.gz`, puis enregistre les
événements trouvés dans PostgreSQL.

Le tableau de bord affiche les échecs par pays, les connexions réussies par
utilisateur et les tentatives faites avec un utilisateur invalide.

## Installation

Il faut installer Python et PostgreSQL, avec l’outil `psql`. Matplotlib est la
seule dépendance Python externe :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
createdb log_analyser
```

Je configure ensuite la connexion PostgreSQL dans PowerShell :

```powershell
$env:PGHOST = "localhost"
$env:PGDATABASE = "log_analyser"
$env:PGUSER = "postgres"
$env:PGPASSWORD = "votre_mot_de_passe"
```

## Lancement

Les journaux sont lus depuis le dossier `data`. Pour associer les adresses IP
à un pays, il faut fournir un fichier `data/ip_country.csv` avec les plages
réseau et les pays correspondants. Une adresse sans correspondance sera
affichée comme `Unknown`.

Pour lancer le programme :

```powershell
python main.py
```

Les résultats sont enregistrés dans la table `auth_events`. Le graphique est
créé dans `reports/dashboard.png` et les erreurs sont écrites dans
`logs/application.log`.

Je peux lancer les tests avec cette commande :

```powershell
python -m unittest discover -s tests -v
```
