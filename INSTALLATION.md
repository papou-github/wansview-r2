# Wansview R2 pour Home Assistant — 0.1.1 expérimentale

Cette première intégration reprend le client Python ayant récupéré la vidéo
CAMSAM en 2304 × 1296. Elle reste à valider dans ton Home Assistant.
Elle utilise le compte Wansview Cloud, puis les relais Internet AJCloud.
Ce n’est pas une connexion vidéo entièrement locale.

## Installation dans Home Assistant OS

1. Extraire l’archive sur le PC.
2. Copier **le dossier `wansview_r2` situé dans `custom_components`** vers
   **`/config/custom_components/`** de Home Assistant, avec Samba ou Studio Code.
   Le résultat doit être :
   **`/config/custom_components/wansview_r2/manifest.json`**.
   Ne pas copier seulement les fichiers dans `custom_components`, ni créer un
   double niveau `wansview_r2/wansview_r2`.
3. Redémarrer Home Assistant. Il installe la dépendance PyNaCl automatiquement.
   Ne pas créer de venv et ne pas exécuter pip dans Home Assistant.
4. Ouvrir **Paramètres → Appareils et services → Ajouter une intégration**.
5. Rechercher **Wansview R2 (expérimental)**.
6. Saisir les identifiants Wansview Cloud et sélectionner **CAMSAM** pour commencer.

Les identifiants sont enregistrés dans la configuration de Home Assistant.
Ils ne sont pas inclus dans les journaux de cette intégration ni dans ses diagnostics.
L’ajout vérifie le compte et la liste des caméras, sans demander de direct.

## Premier essai : image

1. Fermer le direct dans l’application Wansview.
2. Ouvrir l’appareil CAMSAM créé par l’intégration.
3. Appuyer sur **Actualiser l’image**.
4. Attendre la connexion : elle peut prendre plusieurs dizaines de secondes.
5. Afficher l’entité caméra : la nouvelle image doit apparaître.

Le script ferme sa session après avoir reçu et converti la première image clé.
L’image est gardée en mémoire. Les aperçus du tableau de bord ne réveillent pas
la caméra ; après un redémarrage de HA, demander une nouvelle image.

## Deuxième essai : direct

1. Appuyer sur **Direct** pour l’activer.
2. Ouvrir ensuite l’entité caméra pour afficher son direct dans Home Assistant.
3. Utiliser **Direct** pour le désactiver pour arrêter plus tôt.

La fenêtre d’une minute commence à l’appui sur le bouton et inclut le temps
de connexion. Elle ne se prolonge pas automatiquement. Après cette minute,
les tentatives du lecteur HA de se reconnecter ne réveillent pas la caméra.
Fermer le lecteur, réactiver Direct puis rouvrir la caméra pour une
nouvelle session. Ne pas activer « Précharger le flux » dans les options HA.

Le délai HLS du lecteur Home Assistant s’ajoute à la négociation du relais.
Le flux est de la vidéo uniquement. Le son bidirectionnel, le PIR et la batterie
ne sont pas exposés dans cette première version.

## Tableau de bord

Ajouter une carte image-entité en choisissant l’entité caméra CAMSAM depuis
l’éditeur, avec une image fixe (pas `camera_view: live` en permanence).
Ajouter le bouton Actualiser l’image et la commande Direct depuis le sélecteur d’entités.
Utiliser les identifiants effectivement créés par HA : ils dépendent des noms
et d’éventuels doublons déjà présents.

## Connexion et reprises

- Une tentative de négociation sans réponse est retentée une fois avec une
  nouvelle session UDP ; le total reste limité par la fenêtre de la commande.
- Aucune boucle de réveil permanente n’est installée.
- Les deux relais initiaux proviennent de notre capture réussie : leur découverte
  automatique reste à ajouter. Cette dépendance fixe limite la robustesse.
- Ajouter les autres caméras en répétant l’ajout d’intégration une par une après
  validation sur CAMSAM. Chaque entrée correspond à une caméra.
- L’intégration utilise IPv4 pour HTTPS, comme le test fonctionnel sur le PC.
  Le routage et le DNS de la VM HA doivent permettre de joindre AJCloud.
  Le succès depuis le PC sans VPN ne garantit pas le même accès depuis HA.
  Aucune règle pfSense ni route VPN n’est modifiée par cette intégration.

## En cas de problème

Sur l’entité caméra, consulter :

- `connection_state` : `connecting`, `streaming`, `idle` ou `error` ;
- `last_error` : type d’erreur sans message contenant des données sensibles ;
- `connection_attempts`, `frames_received`, `received_bytes`, `image_time` ;
- `cloud_hostname`, si une requête cloud a échoué.

Depuis la page de l’intégration, télécharger ses **diagnostics** et les joindre
à la conversation. Ils excluent les identifiants et les images.
Si l’intégration ne se charge pas, copier l’erreur correspondante dans
**Paramètres → Système → Journaux**.

Si l’image fonctionne mais pas le direct, vérifier d’abord les diagnostics :
la liaison P2P et le lecteur vidéo Home Assistant sont deux étapes différentes.

## Retour arrière

Supprimer l’entrée depuis Appareils et services. Cela ferme la session et le
serveur vidéo local. Le dossier `custom_components/wansview_r2` peut ensuite
être supprimé, puis HA redémarré. Aucun firmware ni réglage caméra permanent
n’est modifié et l’intégration n’écrit aucun fichier vidéo sur disque.

## Vérifications réalisées

- Protocole et authentification issus du client v0.9 réellement testé sur CAMSAM.
- Simulation hors ligne d’une session complète : allocation, authentification,
  vidéo fragmentée et reçue dans le désordre, doublons, arrêt et fermeture UDP.
- Test du serveur HTTP lié uniquement à 127.0.0.1 avec FFmpeg réel : flux MPEG-TS
  décodable, image JPEG, seconde tentative après échec, fermeture des processus.
- Vérification qu’un accès au lecteur à l’arrêt ne provoque aucun réveil cloud,
  et qu’un second appui pendant la session ne prolonge pas sa durée.
- Syntaxe Python et fichiers JSON contrôlés.

L’installation et le lecteur HLS n’ont pas été testés dans une instance HA
complète depuis l’environnement de développement. Ce sera notre prochain test.

Références API consultées :
https://developers.home-assistant.io/docs/core/entity/camera/
https://developers.home-assistant.io/docs/creating_component_index/

## Mise à jour depuis 0.1.0 — commande unique Play/Stop

Remplacer les fichiers du dossier `/config/custom_components/wansview_r2/`
par ceux du dossier `custom_components/wansview_r2` de cette archive, puis
redémarrer Home Assistant. Ne pas supprimer ni réajouter le compte.

Les anciens boutons Démarrer et Arrêter sont retirés du registre de cette
intégration. La nouvelle entité switch « Direct » remplace les deux :
arrêt = icône Play ; connexion/direct en cours = icône Stop. Elle revient à
l’arrêt à la fin de la minute ou en cas d’échec. Actualiser l’image est conservé.

Retirer les deux anciennes cartes du tableau de bord et ajouter la nouvelle
entité Direct. Pour une carte bouton : choisir Direct, action au toucher
« Basculer », et laisser l’icône automatique pour afficher Play/Stop.
