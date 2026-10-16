# Publier le dépôt personnalisé HACS

Dépôt configuré : https://github.com/papou-github/wansview-r2
Responsable : @papou-github. L’étape de configuration est déjà effectuée.

1. Créer sur GitHub un dépôt public `wansview-r2`, avec Issues activé.
2. Depuis ce dossier sur Ubuntu, exécuter en remplaçant TON_COMPTE :

   ```bash
   python3 configure_repository.py papou-github/wansview-r2
   ```

   Cela renseigne documentation, issue_tracker et codeowners dans le manifest.
3. Envoyer **le contenu** de ce dossier à la racine du dépôt : `hacs.json`,
   `README.md` et `custom_components` doivent être directement à la racine,
   sans dossier parent supplémentaire. Inclure également les autres fichiers.
4. Définir une description et les topics `home-assistant`, `hacs`, `wansview`.
5. Créer une release GitHub `v0.1.3` sur ce contenu. Pas d’archive jointe
   nécessaire : HACS télécharge les fichiers du dépôt.
6. Ajouter son URL dans HACS → ⋮ → Dépôts personnalisés → Intégration.

Le responsable configuré par défaut est le propriétaire GitHub du dépôt.
Si le dépôt est dans une organisation, remplacer codeowners par le compte
GitHub réel chargé de sa maintenance.

Les validations locales ne remplacent pas la validation distante HACS.
Une inclusion au catalogue par défaut est une procédure séparée, nécessitant
notamment les exigences de marque et la revue HACS ; elle n’est pas réalisée.

Documentation :
https://www.hacs.dev/docs/publish/integration/
https://www.hacs.dev/docs/publish/start/
