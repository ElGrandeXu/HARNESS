# Sources et choix de conception

Références techniques consultées le 29 octobre 2026. Les pages évoluent : vérifier
l'aide de la CLI installée et le chargement effectif avant d'activer un profil.
Les seuils 80 lignes / 8 Kio, métadonnées JSON, commandes, verrou et manifeste de
proposition sont des conventions locales V1, pas des standards fournisseurs.

- [Synthèse de conception intégrale](reference/Architecture_Agent_Harness_Memoire_Boucles.md) : référence fournie pour l'architecture, avec ses sources primaires et exemples. Aucun import systématique au démarrage.
- [OpenAI — AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) : instructions de dépôt pour Codex. Le profil livré utilise ces instructions et des opérations explicites ; aucun hook Claude n'est transposé.
- [Claude Code — mémoire et imports](https://code.claude.com/docs/en/memory) : adaptateur CLAUDE.md important AGENTS.md et contrôle via /context.
- [Claude Code — hooks](https://code.claude.com/docs/en/hooks) : SessionStart, événements et hookSpecificOutput.additionalContext. Le hook V1 garde son injection sous 10 000 caractères pour rester directement inline.
- [Claude Code — réglages](https://code.claude.com/docs/en/settings-reference) : désactivation optionnelle de l'auto-mémoire via autoMemoryEnabled dans le profil gouverné.
- [GitHub — secrets dans Actions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets) : la CI ne demande aucun secret et n'invoque aucun modèle.
- [actions/checkout](https://github.com/actions/checkout) et [actions/setup-python](https://github.com/actions/setup-python) : actions officielles épinglées par empreinte, avec permissions de lecture seules.

Les exemples sont fictifs et séparés des données initiales. Le code du socle est
original et utilise uniquement la bibliothèque standard Python. Aucune mémoire,
configuration privée ou dépendance à un workspace de construction n'est livrée.
