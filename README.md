J'ai réalisé ce projet pour analyser les connexions SSH à partir de fichiers .log et .gz.

Le programme récupère les informations des connexions et les enregistre dans une base de données PostgreSQL.
Grâce au tableau de bord, je peux voir :
Les connexions échouées par pays.
Les connexions réussies par utilisateur.
Les tentatives avec un utilisateur invalide.

Pour utiliser le projet, il faut installer Python et PostgreSQL.
Ensuite, je configure la connexion à PostgreSQL