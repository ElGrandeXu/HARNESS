@AGENTS.md

# Adaptateur Claude Code

Le profil facultatif est documenté dans docs/PROFILES.md. Aucun hook n'est actif
par défaut. S'il fournit HARNESS_CONTEXT_V1 au démarrage, ne pas exécuter context
une seconde fois. Ne pas importer memory/MEMORY.md ici. Vérifier le chargement
réel avec /context et les hooks avec /hooks. Aucun hook Stop n'est fourni : les
checkpoints se font pendant le travail, pas après toutes les réponses simples.
