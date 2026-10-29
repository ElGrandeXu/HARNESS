# Vérifications et limites de portée

## Exécuter les contrôles

```sh
python3 scripts/harness.py init
python3 scripts/harness.py validate
python3 -m unittest discover -s tests -v
python3 scripts/check_public.py
```

La suite crée des copies temporaires avec chemins contenant des espaces et appelle
la vraie CLI Python. Elle ne modifie pas la mémoire du workspace courant. Les
fichiers de projet fictif et les sorties sont détruits avec les copies temporaires.
Aucun appel LLM, compte GitHub ou secret n'est nécessaire aux tests locaux.

## Scénarios couverts

- Installation vierge, réinitialisation sans écrasement et indépendance du cwd.
- Diagnostic avec PATH vide, lecture ciblée, provenance et formats non supportés.
- Index trop long, lien cassé, ID dupliqué, source absente et statut incohérent.
- Verrou concurrent, comparaison de révision et immutabilité des décisions acceptées.
- Projet CSV fictif : ingestion, tâche, vrai contrôle du CSV, preuve, checkpoint,
  reprise dans un nouveau processus ; le même contrôle échoue sur un CSV dégradé.
- Proposition sans écriture canonique, contradiction potentielle, ajout rendant la
  base périmée, instantané altéré, source manquante et règles stables refusées.
- Hook SessionStart exécuté comme programme avec événements JSON fixtures :
  lecture bornée, déduplication, compaction, erreur non bloquante et absence de Stop.
- Échecs et timeout des vérifications ; une CLI indisponible ne bloque pas le socle.

Le diagnostic d'une CLI qui dépasse son délai utilise un mock explicite. Les
autres tests de hooks utilisent des événements simulés, pas une session Claude.
Le scénario CSV est une exécution réelle locale, pas un test d'intégration LLM.
Le contrôle check_public est une recherche de motifs et de chemins privés dans les
fichiers sélectionnés ; il ne garantit pas l'absence de toute information sensible.
L'option `--template` exige en plus l'absence de données projet distribuées. Elle
sert à qualifier le template vierge, pas à interdire aux étudiants de partager
ensuite des notes sélectionnées et expurgées.

## Plateformes

| Plateforme | Prérequis / portée |
|---|---|
| Linux | Python 3.10+ ; contrôles locaux qualifiés sous Python 3.12.3. |
| macOS | Python 3.10+ installé ; mêmes scripts stdlib ; qualification via la matrice CI, pas de test manuel local. |
| Windows | Python 3.10+ (`py -3` ou `python`) ; chemins avec espaces gérés ; création de symlink peut être ignorée si privilège absent. |
| WSL | Profil Linux ; ne pas confondre avec un test du hook sous shell Windows natif. |

La CI exécute la suite sur les trois OS et sur Python 3.10 pour le minimum annoncé.
Consulter le statut de la CI du commit livré : une matrice configurée n'est pas une
preuve qu'elle a déjà réussi. Aucune intégration interactive Claude Code ou
session de modèle Codex ne fait partie de cette CI. La présence de Codex et son
aide locale sont vérifiées par doctor, sans lancement de tâche modèle.

## Limites assumées

La CLI contrôle la structure et les révisions, pas la vérité des sources, le sens
des contradictions ou la qualité métier des livrables. Les liens HTTP ne sont pas
requêtés ; ancres et syntaxe Markdown complexe demandent une revue. Les budgets
de tâches sont appliqués par l'agent, pas un ordonnanceur automatique.

Les verrous sont coopératifs et locaux. Un éditeur externe peut contourner le
protocole ; une panne disque n'est pas une transaction distribuée. Les hooks ne
sont pas une sandbox. Aucun fichier d'instructions ne peut garantir que tous les
agents respecteront le protocole ou résisteront à une injection malveillante.
Le contrôle des permissions appartient à l'outil et à l'environnement réel.

La consolidation offline fait du tri déterministe ; l'agent prépare les
changements sémantiques, puis une revue décide de l'intégration. Elle ne rend pas
le modèle plus intelligent et ne remplace pas la validation du responsable.
