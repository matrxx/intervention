# Import de la liste des locaux (Versailles et Louvre)

Menu **Administration → Importer la liste des locaux**, réservé aux administrateurs.
Le même fichier peut contenir les deux sites : chaque ligne indique son site.

## Format du fichier

CSV, une ligne par salle. Excel : *Fichier → Enregistrer sous → CSV (séparateur : point-virgule)*. Les fichiers UTF-8 et ceux d'Excel Windows sont acceptés, avec un séparateur point-virgule ou virgule.

| Colonne | Obligatoire | Contenu | Exemple |
|---|---|---|---|
| `site` | oui | `versailles` ou `louvre` | `versailles` |
| `zone` | oui | Code de l'aile ou de la zone. Créée automatiquement si elle n'existe pas. | `G` |
| `zone_nom` | non | Nom affiché de la zone | `avenue de Paris` |
| `niveau` | oui | Libellé du niveau, tel qu'il sera affiché | `1er étage` |
| `ordre_niveau` | non | Ordre de tri des niveaux. Vide : déduit du libellé (−1 sous-sol, 0 RDC, 1 entresol, 2 pour le 1er étage, 3 pour le 2e…) | `2` |
| `code` | oui | Code de la salle, unique dans un site | `G109` |
| `libelle` | non | Nom d'usage de la salle | `Atelier peinture couche picturale GF` |
| `active` | non | `oui` ou `non` (vide = oui). Une salle inactive n'est plus proposée à la saisie. | `oui` |

Les lignes qui commencent par `#` sont ignorées, ce qui permet d'y laisser des notes.

Fichiers fournis :
- `modele_import_locaux.csv` : en-têtes et exemples en commentaire, à remplir (aussi téléchargeable depuis la page d'import) ;
- `locaux_versailles.csv` : les 116 salles de Versailles, déjà dans ce format, à compléter puis réimporter.

## Déroulement

1. **Exportez** la liste actuelle (bouton « Exporter ») : c'est le meilleur point de départ, déjà au bon format.
2. Modifiez-la dans Excel : complétez les libellés, ajoutez les salles du Louvre, passez `active` à `non` pour une salle condamnée.
3. **Déposez** le fichier et choisissez le mode :
   - *Ajouter et mettre à jour* : les salles du fichier sont créées ou modifiées ; les autres ne changent pas ;
   - *Remplacer la liste* : en plus, les salles d'un site présent dans le fichier mais absentes du fichier sont **désactivées**. Un site absent du fichier n'est pas touché.
4. **Vérifiez l'aperçu** : nombre de salles nouvelles, modifiées, inchangées, désactivées, ou la liste des erreurs avec leur numéro de ligne. Rien n'est modifié à cette étape.
5. **Confirmez l'import.**

Les salles ne sont jamais supprimées, pour conserver l'historique des interventions qui les citent. Pour retirer une salle de la saisie, désactivez-la.

En ligne de commande (même contrôle, aperçu par défaut) :

```bash
sudo docker compose exec web python manage.py importer_locaux /app/docs/locaux_versailles.csv              # aperçu
sudo docker compose exec web python manage.py importer_locaux /app/docs/locaux_versailles.csv --appliquer  # import
```
