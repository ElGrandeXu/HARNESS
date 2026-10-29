# Architecture V1

```text
AGENTS.md / CLAUDE.md        Contrat stable et adaptateur, sans mémoire personnelle
START_HERE.md               Prompt et parcours d'installation
inbox/                      Documents utilisateur ignorés ; brief libre
templates/                  États vierges et préférences exemples
memory/                     Index court, décisions, topics, incidents, archives
tasks/                      Résultats attendus et critères observables
handoffs/                   CURRENT et transmissions de sessions uniques
scripts/harness.py          Mécanismes locaux déterministes
profiles/claude/             Hook facultatif, jamais activé par init
.agent-state/               Reçus, brouillons, propositions et verrous locaux
docs/                       Usage, limites et référence complète à la demande
examples/ / tests/          Fiction isolée et tests en copies temporaires
```

Les données de projet ne sont pas versionnées automatiquement. Les README des
dossiers restent publics ; init crée des états vierges locaux. Ce choix protège
les documents étudiants dès le premier fork, au prix d'une sélection explicite
avant chaque premier partage d'une note. Après sélection, Git assure l'historique.

La mémoire dit ce qu'on sait et pourquoi ; la tâche dit ce qu'il faut obtenir ;
le handoff dit où reprendre ; la preuve dit ce qui a été exécuté. Aucun de ces
fichiers ne peut s'accorder une autorité supérieure aux instructions de l'utilisateur.
Les instructions stables n'absorbent ni les journaux ni les résumés automatiques.

Le socle ne contient aucun agent autonome en arrière-plan. La boucle est suivie
par l'agent au moyen des instructions et des contrôles explicites, avec limites
par tâche. La CLI fournit les opérations fiables, pas le raisonnement métier.
La consolidation est un artefact révisable sur une base d'empreintes ; sa validation
syntaxique ne vaut ni approbation humaine ni preuve de vérité.

La [synthèse de conception](reference/Architecture_Agent_Harness_Memoire_Boucles.md)
est conservée intégralement comme référence, sans import au démarrage. Les seuils
et formats V1 sont des conventions de ce dépôt, pas des standards des fournisseurs.
