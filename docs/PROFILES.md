# Profils : ce qui est automatique et ce qui ne l'est pas

| Fonction | Codex | Claude Code | CLI locale |
|---|---|---|---|
| Instructions stables | AGENTS.md selon la portée native | CLAUDE.md importe AGENTS.md | Aucun modèle |
| Index + checkpoint | L'agent exécute context par instruction | Même protocole, ou SessionStart facultatif | Lecture bornée |
| Boucle tâche/vérification/correction | Instruction, pas moteur automatique | Instruction, pas hook Stop | Reçus et budgets descriptifs |
| Écriture mémoire / checkpoint | L'agent appelle les commandes | L'agent appelle les commandes | Verrou + contrôle de révision |
| Consolidation | Explicite | Explicite | Proposition offline uniquement |

## Codex

Ouvrir le dépôt comme workspace ou utiliser `codex --cd CHEMIN` si l'aide de votre
version expose --cd. Vérifier `codex --help` avant de copier cette option.
Le fonctionnement minimal repose sur AGENTS.md et des commandes explicites, tel
que documenté par [OpenAI](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
Aucun hook Claude n'est copié dans la configuration Codex. Ce dépôt ne prétend
pas que Codex manque de hooks : aucun profil de hooks Codex n'a été qualifié ici.
Les permissions/globales et les instructions parentes peuvent influer sur l'agent.
AGENTS.local.md est lu par instruction du dépôt, pas par un nom natif garanti.

## Claude Code : profil facultatif SessionStart

Aucun réglage .claude actif n'est livré. Examiner profiles/claude/bootstrap.py et
settings.example.json. Le profil désactive l'auto-mémoire native du projet pour
ne garder qu'une mémoire gouvernée. L'adaptateur importe uniquement AGENTS.md ;
il n'importe ni l'index ni CURRENT.

Après revue, fusionner le contenu du fichier exemple dans .claude/settings.json.
Ne pas écraser un fichier existant ni doubler un hook déjà configuré. Le réglage
local reste ignoré par Git. init n'active rien et ne modifie aucun réglage global.
L'exemple utilise python3 et le shell avec ${CLAUDE_PROJECT_DIR} ; pour Windows
natif adapter la commande au shell configuré et à `py -3`, puis tester. WSL suit
le profil Linux. Ne pas annoncer ce profil natif Windows comme testé.

Le hook ne lance aucune CLI ni processus récursif, ne configure aucun droit, ne
fait aucune consolidation et ne contient aucun Stop. Il renvoie un contexte court
lors de startup/resume/clear/compact (40 lignes et 4 000 octets par fichier).
Une troncature est signalée ; consulter explicitement la suite si nécessaire.
Les répétitions d'un même événement inchangé
sont dédupliquées ; une nouvelle compaction avec un transcript différent reçoit
une nouvelle génération. Si le transcript est inaccessible, compact/clear force
une nouvelle génération pour ne pas perdre le contexte ; dans ce cas la stricte
déduplication d'événements répétés n'est pas garantie.

Les erreurs du hook donnent un message diagnostique sur stderr et laissent
continuer l'agent avec le protocole explicite. Elles ne bloquent pas une session.
Une sortie réussie ne prouve pas que le modèle a bien appliqué le contexte.

Contrôler `claude --help`, `claude --version`, puis /hooks et /context après
activation. Vérifier qu'un seul HARNESS_CONTEXT_V1 est fourni par génération et
que CLAUDE.md charge AGENTS.md. La CLI Claude n'était pas installée sur la machine
de construction : le hook est testé comme programme, pas en intégration réelle.
Voir les [hooks officiels](https://code.claude.com/docs/en/hooks),
[réglages](https://code.claude.com/docs/en/settings-reference) et
[imports mémoire](https://code.claude.com/docs/en/memory).

## Profils avancés non activés

Pas de planificateur, LLM headless, appel payant, auto-apply ou évaluateur séparé.
Ajouter un tel profil seulement si un besoin observé le justifie, avec outil et
options vérifiés, budget, permissions et tests propres au projet. Le socle reste
entièrement utilisable sans ces extensions et sans authentification fournisseur.
