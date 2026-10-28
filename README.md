# The Echo of a Silence — site de livre

Site web Flask/Python pour présenter **The Echo of a Silence**, d’Antoine Christopher, permettre la lecture PDF dans le navigateur et le téléchargement d’un fichier PDF ou EPUB. Le tableau de bord affiche les statistiques, avec une base de départ de **800 vues**, **264 téléchargements**, **137 lecteurs** et **42 partages**.

> Transparence : les nombres de départ sont des valeurs initiales demandées pour le design. À partir du déploiement, les visites, lectures et téléchargements du site sont incrémentés par les événements réellement enregistrés. Le graphique montre les événements réellement comptés sur les 7 derniers jours ; il peut donc commencer à zéro.

## Lancer en local

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
export ADMIN_PASSWORD="choisir-un-mot-de-passe-solide"
python app.py
```

Ouvre `http://127.0.0.1:5000`. Sur Windows PowerShell, utilise `$env:ADMIN_PASSWORD="choisir-un-mot-de-passe-solide"`.

## Publier le livre

1. Ouvre `/admin`.
2. Saisis le mot de passe configuré avec `ADMIN_PASSWORD`.
3. Sur l’écran suivant, saisis de nouveau le mot de passe et choisis le fichier PDF ou EPUB.
4. Le fichier publié apparaît sur la page principale. Le bouton « Lire en ligne » s’affiche pour un PDF ; le bouton « Télécharger » fonctionne pour PDF et EPUB.

## Déployer sur GitHub + Render

1. Crée un dépôt GitHub et téléverse tous les fichiers de ce dossier.
2. Sur Render, choisis **New + → Blueprint** puis connecte le dépôt ; Render détectera `render.yaml`.
3. Dans les variables d’environnement du service Render, définis `ADMIN_PASSWORD` avec un mot de passe solide. `SECRET_KEY` est générée par le Blueprint.
4. Déploie et ouvre l’URL Render fournie.

### IMPORTANT — persistance sur Render

Le système de fichiers d’un service web Render standard peut être éphémère : sans disque persistant, la base SQLite et les fichiers uploadés peuvent disparaître lors d’un redéploiement ou d’un redémarrage. Pour conserver le livre et les statistiques :
- ajoute un **Persistent Disk** dans Render (par exemple monté sur `/var/data`);
- définis `UPLOAD_FOLDER=/var/data/uploads` et `DATABASE_PATH=/var/data/booksite.db`;
- crée le dossier `uploads` sur le disque si nécessaire. Si ton plan Render ne permet pas les disques persistants, héberge le livre dans un stockage durable externe ou dans le dépôt (fichier public statique) et choisis une base de données persistante.

## Personnalisation

Variables facultatives : `BOOK_TITLE`, `BOOK_AUTHOR`, `BOOK_DESCRIPTION`, `UPLOAD_FOLDER`, `DATABASE_PATH`, `SECRET_KEY`, `ADMIN_PASSWORD`.

## Notes de sécurité

- Ne mets jamais ton mot de passe administrateur dans le code ou sur GitHub.
- Change `SECRET_KEY` en production (le Blueprint la génère automatiquement).
- La page d’administration utilise une vérification simple à chaque requête ; pour un projet public plus important, ajoute une authentification avec session sécurisée, limitation de tentatives et stockage persistant.
- Les statistiques « partages » sont une valeur de départ visuelle pour l’instant ; le site ne prétend pas mesurer les partages externes.
