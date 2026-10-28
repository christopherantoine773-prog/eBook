# Correction du stockage — The Echo of a Silence

## Important
Cette version du `app.py` choisit `/var/data` sur Render si ce dossier existe. Pour que les vues et le livre restent réellement sauvegardés après redémarrage/redéploiement, il faut attacher un **Persistent Disk** au service Render et définir son point de montage sur `/var/data`. Sans disque persistant (ou base de données externe), le code seul ne peut pas garantir la conservation des données.

## Configuration Render
1. Ouvrir le service Web Render du site.
2. Dans **Disks**, créer/attacher un disque persistant avec le point de montage `/var/data`.
3. Dans **Environment**, définir :
   - `DATABASE_PATH` = `/var/data/booksite.db`
   - `UPLOAD_FOLDER` = `/var/data/uploads`
   - conserver les variables déjà utilisées, notamment `ADMIN_PASSWORD` et `SECRET_KEY`.
4. Redéployer le site.

## Fichiers
Remplacer le `app.py` actuel par celui-ci et conserver le reste du projet : `templates/`, fichiers CSS/images, etc. Ne déployer pas uniquement ce ZIP, car il ne contient pas les modèles HTML du site.

## Données déjà disparues
Ce correctif protège les données futures après configuration du disque. Il ne peut pas recréer les compteurs ou fichiers déjà perdus. Si l’ancienne base de données est encore disponible, la copier vers `/var/data/booksite.db` avant de basculer.

Le graphique de l’accueil est codé pour afficher les événements des 7 derniers jours ; les anciens événements ne s’affichent donc plus dans ce graphique, même si le compteur global continue de les compter.
