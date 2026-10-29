# Commandes, formats et reprise

Toutes les commandes acceptent `--help`. Depuis un autre répertoire, utiliser le
chemin du script : `python3 "/chemin/du projet/scripts/harness.py" init`.
La racine vient du script, jamais du cwd. `--root CHEMIN` permet de cibler une
copie explicite ; il se place avant le sous-ordre. Aucun reset n'existe.

## Commandes locales

| Commande | Effet |
|---|---|
| `init` | Crée index, état vierge et configuration absents ; ne remplace rien. |
| `doctor` | Validation locale et sondes `--help` / `--version` des CLI optionnelles ; aucun modèle. |
| `validate` | Vérifie mémoire, tâches et sessions ; sort avec code 1 en cas d'erreur. |
| `inventory` | Métadonnées des documents inbox/, sans en charger le contenu. |
| `read CHEMIN --start 1 --lines 80` | Lecture ciblée UTF-8, 200 lignes et 64 Kio maximum par fichier. |
| `ingest inbox/BRIEF.md` | Reçu de provenance + extrait ; aucune extraction sémantique automatique. |
| `context [--session GENERATION]` | Index + CURRENT, chacun borné à 80 lignes et 8 Kio. |
| `task ...` | Nouvelle tâche todo, sans preuve ni réussite présumée. |
| `verify --timeout 60 -- PROGRAMME ARGUMENTS` | Exécute un contrôle et produit un reçu ; code 1 si échec/timeout. |
| `revision CHEMIN` | SHA256 courant ou `absent`. |
| `put CHEMIN --source BROUILLON --expected SHA` | Écriture mémoire/tâche validée et conditionnelle. |
| `checkpoint ... --expected SHA` | Transmission unique, puis mise à jour atomique de CURRENT. |
| `consolidate --source CHEMIN` | Proposition locale avec instantanés, jamais intégrée. Répéter --source. |
| `proposal-check CHEMIN` | Vérifie péremption, sources et éventuels changements proposés ; n'applique rien. |

Les tailles sont en octets UTF-8, pas en tokens. context lit au plus 8193 octets
par entrée et signale une troncature. Sans --session il imprime le contexte pour
une lecture explicite ; l'agent ne doit pas le redemander si le marqueur existe.
Avec --session, une génération inchangée n'est pas injectée deux fois. Après une
compaction, utiliser une nouvelle génération. Ne pas garder un identifiant global
qui empêcherait une session fraîche de recevoir son contexte.

## Exemple de tâche et preuve réelle

```sh
python3 scripts/harness.py task --id TASK-001 --goal "Vérifier le livrable" --scope "livrable" --owner "student" --acceptance "Le contrôle ciblé réussit" --verification "commande adaptée au projet"
python3 scripts/harness.py verify --timeout 60 -- python3 scripts/harness.py validate
python3 scripts/harness.py revision tasks/TASK-001.md
```

verify ne valide ici que la structure du harness. Remplacer le contrôle par une
vraie vérification des critères du projet. Le reçu contient commande, code retour,
sorties bornées, date, base Git et liste des modifications, pas une approbation
métier. Les arguments et sorties peuvent être sensibles : ne pas y mettre de clé.
Un timeout arrête le processus direct, pas nécessairement ses descendants ; ne
pas lancer de service permanent via verify. Le stockage temporaire de la sortie
n'a pas de quota disque ; choisir un contrôle borné. Aucune sandbox n'est ajoutée.

Pour modifier la tâche, copier son contenu dans .agent-state/task-draft.md, modifier
les métadonnées, ajouter le chemin du reçu à evidence, puis utiliser put avec la
révision lue AVANT la préparation. done exige au moins une preuve au code 0 ;
l'agent doit vérifier en plus la correspondance aux critères et la fraîcheur.
Une modification concurrente produit « Base périmée », jamais un écrasement.

## Format des notes

Les fichiers .md structurés commencent par un objet **JSON**, entre deux lignes
`---`. Ce n'est pas du YAML : aucun parseur externe n'est nécessaire. Exemple
isolé : [examples/MEM-note.md](../examples/MEM-note.md).
Les fins de ligne LF et CRLF ainsi qu'un BOM UTF-8 sont acceptés à la lecture ;
les empreintes de provenance et de révision portent toujours sur les octets réels.

| Entité | Champs requis |
|---|---|
| Mémoire | id, type, status, scope, statement, reason, source[], evidence[], last_verified, review_when, supersedes[] |
| Tâche | id, status, goal, scope, acceptance[], verification, owner, evidence[], retry_limit, time_budget_minutes |
| Session | id, status, task, summary, next, evidence[], base, changes[] |

Identifiants globaux : MEM-*, TASK-*, SESSION-* ; suffixes alphanumériques, tirets
et underscores, 80 caractères maximum. Les IDs doivent rester uniques, même dans
archive/. Les sources et preuves mémoire sont des URLs HTTP(S) ou des chemins
relatifs à la racine. Leurs fragments/ancres et le contenu web ne sont pas validés
par validate ; les chemins locaux doivent exister. Dans le corps Markdown, les
liens sont relatifs au fichier et contrôlés hors blocs de code. Les liens Markdown
complexes, références indirectes et images nécessitent une revue humaine.

Types/statuts : fact/observed, decision/accepted, hypothesis/unconfirmed,
incident/open ou observed. superseded reste disponible pour les notes anciennes.
Une date last_verified valide et une condition review_when sont requises ; cela
ne rend pas un fait éternel. Une décision acceptée doit citer une confirmation
réelle. supersedes référence un ID existant sans effacer l'ancien document.
Les sources textuelles libres sans chemin/URL ne sont pas des preuves suffisantes.

## Checkpoint et reprise

```sh
python3 scripts/harness.py revision handoffs/CURRENT.md
python3 scripts/harness.py checkpoint --expected SHA_LU --task TASK-001 --summary "Contrôle exécuté ; reste à vérifier le livrable réel" --next "Exécuter le contrôle métier" --evidence .agent-state/evidence/RECU.json
```

Reprendre : context, ouvrir la session liée et la tâche, vérifier Git et les
fichiers, relire la preuve, puis exécuter l'action suivante si elle est encore
pertinente. Un crash entre session et CURRENT laisse la session récupérable sous
handoffs/sessions/. CURRENT n'est pas mis à jour si sa base a changé.

## Consolidation maîtrisée

Sélectionner un delta explicite (maximum 20 sources, 256 Kio cumulés). consolidate
copie les sources et enregistre une base d'empreintes incluant mémoire, tâches,
sessions, AGENTS.md, CLAUDE.md et project.local.json. Les ajouts et suppressions
canoniques rendent la proposition périmée, pas seulement les modifications.

Le rapport suggère des doublons exacts et des contradictions **potentielles** par
périmètre. Des affirmations différentes ne sont pas forcément contradictoires.
Il ne résout rien sémantiquement, n'appelle aucun modèle et laisse changes vide
par défaut. L'agent peut compléter la proposition avec des changements exacts :

```json
{
  "path": "memory/topics/MEM-nouveau.md",
  "before_sha256": "absent",
  "after": "contenu Markdown complet avec métadonnées JSON",
  "reason": "information durable évitant une redécouverte",
  "sources": ["inbox/BRIEF.md"],
  "status": "proposed"
}
```

Chaque source de changement doit faire partie des instantanés. proposal-check
contrôle le contenu proposé sans l'écrire. Relire le diff et les contradictions,
conserver les anciens IDs et preuves, puis utiliser put pour chaque note autorisée
et mettre à jour l'index en dernier. Recalculer une proposition si sa base est
périmée. Il n'y a volontairement ni commande apply globale ni réécriture automatique.
Une décision acceptée se remplace par une nouvelle décision sourcée avec supersedes,
jamais par une modification silencieuse de l'ancienne. Une proposition ne modifie
pas les règles stables.

## Concurrence et erreurs

Toutes les mutations CLI utilisent un verrou local commun (.agent-state/write.lock),
une écriture temporaire + os.replace, et une comparaison de révision pour les
fichiers existants. put ne supprime aucun fichier. checkpoint écrit une session
unique avant CURRENT. Les écritures manuelles ne sont pas protégées : les agents
doivent respecter ce protocole ; ce n'est pas une frontière de sécurité OS.

En cas de verrou abandonné, lire owner.json et vérifier qu'aucune opération n'est
encore active sur cette machine avant de retirer manuellement ce seul verrou.
Aucune suppression automatique fondée sur l'âge. Des clones/worktrees séparés
n'ont pas un verrou distribué ; intégrer leurs notes par revue Git.
