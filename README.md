# The Echo of a Silence — bibliothèque de livres

Site Flask/Python pour présenter les livres d'Antoine Christopher. La bibliothèque accepte plusieurs fichiers PDF et EPUB. Ajouter un titre ne remplace pas les livres déjà publiés.

## Lancer en local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ADMIN_PASSWORD="choisir-un-mot-de-passe-solide"
export SECRET_KEY="une-cle-secrete-longue-et-aleatoire"
python app.py
```

Ouvre `http://127.0.0.1:5000`, puis `/admin` pour te connecter et ajouter un livre. Pour chaque livre, renseigne son titre, son auteur, sa description et son fichier PDF ou EPUB (50 Mo maximum). Les PDF peuvent être lus dans le navigateur; les PDF et EPUB peuvent être téléchargés.

## Déploiement Render

1. Téléverse tout le contenu du dossier sur GitHub.
2. Sur Render, crée le service Web depuis ce dépôt.
3. Définis `ADMIN_PASSWORD` et une valeur forte pour `SECRET_KEY`.
4. **Pour conserver les livres et les statistiques**, ajoute un Persistent Disk sur Render, monté sur `/var/data`, puis configure :
   - `DATABASE_PATH=/var/data/booksite.db`
   - `UPLOAD_FOLDER=/var/data/uploads`

Sans disque persistant, le système de fichiers d'un service web peut être réinitialisé au redémarrage ou au redéploiement. Le code ne peut pas récupérer des fichiers ou statistiques déjà perdus. La migration de l'ancienne base, si elle est encore présente dans le dossier de données, conserve l'ancien livre et ses compteurs globaux.

## Statistiques

Les compteurs globaux commencent avec les valeurs de départ du design (800 vues, 264 téléchargements, 137 lecteurs et 42 partages). Les événements ultérieurs sont enregistrés dans SQLite. Les statistiques individuelles de chaque livre comptent les vues de la page d'accueil lorsqu'il est le premier titre, les lectures et les téléchargements. Le graphique montre les événements réels des sept derniers jours. Le compteur de partages reste une valeur initiale et ne mesure pas les partages externes.

## Sécurité

Ne mets pas `ADMIN_PASSWORD` ou `SECRET_KEY` dans le dépôt GitHub. Le panneau d'administration utilise une session après connexion; protège le mot de passe et configure HTTPS en production.
