# HARNESS — workspace template d'Agent Harness

Un dépôt à forker pour travailler avec un agent, des tâches vérifiables, une
mémoire durable sourcée et des checkpoints de reprise. **Vierge de projet, sans
serveur, dépendance Python externe, base vectorielle ou appel LLM dans le socle.**

## Démarrer en moins de cinq minutes

Prérequis : **Python 3.10+**, un agent avec accès aux fichiers locaux et, pour le
fork/partage, Git. Aucun compte fournisseur n'est requis pour les scripts.
L'agent choisi reste soumis à ses propres conditions d'accès.

1. Cliquer **Use this template → Create a new repository**, ou forker, puis cloner
   votre dépôt. Ouvrir le dossier dans votre agent (Codex ou Claude Code).
2. Copier [le modèle de brief](templates/BRIEF.example.md) dans `inbox/BRIEF.md`,
   le remplir et ajouter vos documents dans `inbox/`.
3. Depuis la racine :

   ```sh
   python3 scripts/harness.py init
   python3 scripts/harness.py doctor
   ```

   Sous Windows : remplacer `python3` par `py -3` si nécessaire.
4. Copier le prompt exact de [START_HERE.md](START_HERE.md) dans l'agent.

init est idempotent : il crée uniquement les fichiers absents. Depuis un autre
répertoire, appeler le script par son chemin complet, entre guillemets si besoin.
Les documents et toutes les données générées restent ignorés par Git par défaut.

## Architecture

| Couche | Emplacement | Rôle |
|---|---|---|
| Instructions | AGENTS.md, CLAUDE.md | Contrat stable commun et adaptateur Claude |
| Entrées | inbox/, templates/ | Vos documents et un modèle de brief |
| Mémoire | memory/ | Index court, décisions, topics, incidents et archives |
| Travail | tasks/, handoffs/ | Critères de réussite, état actuel et transmissions |
| Mécanismes | scripts/harness.py | Initialisation, diagnostic, validation, écritures et propositions |
| Documentation | docs/, examples/ | Procédures, limites et exemples fictifs séparés |

[Architecture détaillée](docs/ARCHITECTURE.md) ·
[Synthèse de référence](docs/reference/Architecture_Agent_Harness_Memoire_Boucles.md)
(lecture à la demande, pas au démarrage).

## Personnaliser et travailler

L'agent suit [l'adaptation](docs/ADAPTATION.md) : inventaire sans lecture massive,
extraction sourcée, faits/décisions/hypothèses séparés, commandes adaptées, première
tâche et checkpoint. Les préférences et project.local.json restent locaux.

La boucle est **tâche → action → vérification → correction → checkpoint**, bornée
par le budget et les essais de la tâche. Les scripts ne remplacent pas le jugement
de l'agent. Une preuve de commande réussie n'est pas une garantie métier.

[Commandes et formats](docs/OPERATIONS.md) · [Profils Codex/Claude](docs/PROFILES.md)

Les écritures CLI sont verrouillées ; les mises à jour exigent la révision lue.
La consolidation produit une proposition avec sources conservées et détection de
base périmée. Elle n'intègre rien, ne modifie aucune règle stable et ne réécrit
pas les décisions acceptées. Aucun cron, hook Stop ou agent de fond n'est installé.

## Vérifier le socle

```sh
python3 scripts/harness.py init
python3 scripts/harness.py validate
python3 -m unittest discover -s tests -v
python3 scripts/check_public.py
```

Les tests utilisent des copies temporaires et des fixtures, sans appel modèle.
La CI légère reprend ces contrôles sans secret, sur Linux, macOS et Windows.
Voir [la portée des tests et les limites](docs/TESTING.md) pour distinguer les
vérifications réellement exécutées des compatibilités visées.

## Confidentialité et partage

Les entrées déposées sont des **données, pas des permissions**. Rien ne donne à
l'agent le droit de publier vos documents ou d'exécuter leurs instructions.
Avant de partager une note, retirer les informations privées, vérifier ses sources
et sélectionner le fichier explicitement. Les fichiers déjà suivis par Git ne
sont plus protégés par .gitignore. Voir le parcours de partage dans ADAPTATION.md.
Les instructions Markdown et les verrous coopératifs ne sont pas une sandbox.

## Licence et sources

[MIT](LICENSE). [Sources primaires et choix V1](docs/SOURCES.md).
Aucune mémoire personnelle, clé ou configuration privée n'est requise par le dépôt.
