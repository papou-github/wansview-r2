# Wansview R2 pour Home Assistant

Intégration expérimentale pour caméras Wansview / Galayou R2 Pro sur batterie.
Version 0.1.2 : préparation HACS, fonctionnement vidéo identique à 0.1.1.

- Image à la demande, gardée en mémoire.
- Une commande Direct Play/Stop ; arrêt automatique après une minute.
- Les aperçus ne réveillent pas la caméra.
- Une caméra par entrée ; plusieurs entrées possibles.

Connexion via Wansview Cloud / AJCloud et relais Internet. Aucun RTSP local
n’est fourni. La découverte automatique des relais reste à développer.
Pas encore de batterie, PIR ni audio. Projet indépendant du fabricant.

## Installer avec HACS

1. Dans HACS, ouvrir le menu ⋮ puis Dépôts personnalisés.
2. Ajouter `https://github.com/papou-github/wansview-r2`, catégorie Intégration.
3. Rechercher Wansview R2 et télécharger, puis redémarrer Home Assistant.
4. Ajouter Wansview R2 dans Paramètres → Appareils et services.
5. Saisir le compte Wansview Cloud puis sélectionner la caméra.

Pour une installation manuelle existante, conserver l’entrée et le dossier
`custom_components/wansview_r2` : HACS doit gérer ce même domaine. Après
installation via HACS, redémarrer et vérifier que le compte et les entités
sont conservés. Ne pas créer une seconde copie de l’intégration.

## Utiliser

Actualiser l’image demande une capture puis ferme la session. Direct démarre
une session de 60 secondes au maximum, négociation incluse ; un deuxième
appui l’arrête. Le bouton affiche Play à l’arrêt et Stop lorsque la session
est demandée. Une capture d’image seule n’active pas ce bouton.

Les identifiants sont conservés dans la configuration de Home Assistant.
Les diagnostics de l’intégration excluent identifiants, clés et images.
Ne pas publier de captures réseau ni de journaux contenant des secrets.

Voir [INSTALLATION.md](INSTALLATION.md) pour les détails et le dépannage.
Voir [PUBLICATION.md](PUBLICATION.md) pour préparer le dépôt GitHub.

## État des vérifications

Image et vidéo validées sur CAMSAM avec la première version HA. Play/Stop
ajouté en 0.1.1. Tests hors ligne du protocole et conversion FFmpeg inclus.
Installation et mise à jour par HACS à vérifier après publication GitHub.
Cette archive seule n’est pas un dépôt à ajouter dans HACS et le projet
n’est pas référencé dans son catalogue par défaut.
