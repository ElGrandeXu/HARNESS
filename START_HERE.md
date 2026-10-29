# Démarrer après fork ou « Use this template »

Prérequis : Python 3.10+ et un agent capable de lire/écrire les fichiers locaux.
Git n'est requis que pour le suivi et le partage, pas pour la mémoire locale.

1. Cloner votre fork ou votre dépôt créé depuis le template.
2. Copier templates/BRIEF.example.md vers inbox/BRIEF.md, le remplir et déposer
   les documents utiles dans inbox/. Ils restent ignorés par Git.
3. À la racine, exécuter `python3 scripts/harness.py init` (Windows : `py -3`).
4. Ouvrir l'agent sur ce dépôt et copier exactement ce prompt :

```text
Lis AGENTS.md puis START_HERE.md et docs/ADAPTATION.md. Initialise ce workspace
sans écraser mes personnalisations, inventorie inbox/ et adapte le harness à mon
projet avec les documents pertinents seulement. Source les faits, distingue les
décisions confirmées des hypothèses et ne pose que les questions bloquantes.
Configure les vérifications adaptées, crée une première tâche avec critères
observables et un checkpoint de reprise, puis exécute le diagnostic et la
validation locale. Ne publie aucune donnée ni n'active de service ou d'appel LLM
supplémentaire. Donne le résultat vérifié et la prochaine action utile.
```

Le prompt ne commande pas de réaliser tout le projet immédiatement : il prépare
un environnement adapté et une première étape vérifiable. Si aucun brief n'est
présent ou si l'objectif est incompréhensible, l'agent demande cette information
sans inventer de tâche ni de décision.

La référence de conception est conservée dans docs/reference/ ; elle ne fait
pas partie du contexte de démarrage. Le dépôt fonctionne sans son chargement.
