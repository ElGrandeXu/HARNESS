#!/usr/bin/env python3
"""Local, offline Agent Harness. Python 3.10+, standard library only."""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
MAX_FILE = 65536
LIMITS = {"memory/MEMORY.md": (80, 8192), "handoffs/CURRENT.md": (80, 8192)}
MANAGED = ("memory", "tasks", "handoffs")
ID = re.compile(r"(?:MEM|TASK|SESSION)-[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
LINK = re.compile(r"\[[^\]]*\]\(([^\n)]+)\)")


class HarnessError(Exception):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def path_for(relative):
    """Reject traversal and symlinks, including ones pointing inside the root."""
    relative = str(relative)
    p = Path(relative)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise HarnessError(f"Chemin relatif sûr requis : {relative}")
    target = ROOT / p
    cursor = ROOT
    for part in p.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise HarnessError(f"Lien symbolique refusé : {relative}")
    if not target.resolve().is_relative_to(ROOT):
        raise HarnessError(f"Chemin hors projet : {relative}")
    return target


def read_bytes(relative, limit=MAX_FILE):
    with path_for(relative).open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise HarnessError(f"Taille excessive : {relative} (> {limit} octets)")
    return data


def read_text(relative):
    return read_bytes(relative).decode("utf-8")


def revision(relative):
    p = path_for(relative)
    return digest(read_bytes(relative)) if p.exists() else "absent"


def atomic_write(relative, data):
    p = path_for(relative)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".harness-", dir=p.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data if isinstance(data, bytes) else data.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


@contextlib.contextmanager
def lock():
    state = path_for(".agent-state")
    state.mkdir(exist_ok=True)
    p = path_for(".agent-state/write.lock")
    try:
        p.mkdir()
    except FileExistsError:
        raise HarnessError("Écriture verrouillée. Inspecter .agent-state/write.lock ; "
                           "ne retirer un verrou abandonné qu'après vérification de son propriétaire.")
    try:
        atomic_write(".agent-state/write.lock/owner.json", json_text({
            "pid": os.getpid(), "started": now()}))
        yield
    finally:
        owner = p / "owner.json"
        if owner.exists():
            owner.unlink()
        p.rmdir()


def document(meta, body):
    return "---\n" + json_text(meta) + "---\n\n" + body.rstrip() + "\n"


def parse_document(text, relative):
    if not text.startswith("---\n"):
        raise HarnessError(f"Métadonnées JSON entre --- requises : {relative}")
    try:
        head, body = text[4:].split("\n---\n", 1)
        meta = json.loads(head)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HarnessError(f"Métadonnées JSON invalides : {relative} : {exc}")
    if not isinstance(meta, dict):
        raise HarnessError(f"Objet JSON requis : {relative}")
    return meta, body


def required(meta, names, relative):
    for name in names:
        if name not in meta or meta[name] is None or meta[name] == "":
            raise HarnessError(f"Champ requis {name} : {relative}")


def text_fields(meta, names, relative):
    for name in names:
        if not isinstance(meta.get(name), str) or not meta[name].strip():
            raise HarnessError(f"Champ texte non vide requis {name} : {relative}")


def strings(value):
    return isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value)


def record_check(relative, text, available=()):
    meta, body = parse_document(text, relative)
    required(meta, ("id", "status"), relative)
    text_fields(meta, ("id", "status"), relative)
    if not isinstance(meta["id"], str) or not ID.fullmatch(meta["id"]):
        raise HarnessError(f"Identifiant invalide : {relative}")
    if relative.startswith("tasks/"):
        required(meta, ("goal", "scope", "acceptance", "verification", "owner",
                        "retry_limit", "time_budget_minutes", "evidence"), relative)
        text_fields(meta, ("goal", "scope", "verification", "owner"), relative)
        if not meta["id"].startswith("TASK-") or meta["status"] not in (
                "todo", "doing", "blocked", "done"):
            raise HarnessError(f"Type ou statut de tâche invalide : {relative}")
        if not strings(meta["acceptance"]) or not meta["acceptance"]:
            raise HarnessError(f"Critères d'acceptation requis : {relative}")
        if not strings(meta["evidence"]):
            raise HarnessError(f"evidence doit être une liste de chemins : {relative}")
        for field in ("retry_limit", "time_budget_minutes"):
            if type(meta[field]) is not int or not 1 <= meta[field] <= 1440:
                raise HarnessError(f"Budget invalide {field} : {relative}")
        for ref in meta["evidence"]:
            evidence = json.loads(read_text(ref))
            if not isinstance(evidence, dict) or not evidence.get("kind") == "verification":
                raise HarnessError(f"Preuve invalide : {ref}")
            if meta["status"] == "done" and evidence.get("returncode") != 0:
                raise HarnessError(f"Preuve en échec pour tâche done : {ref}")
        if meta["status"] == "done" and not meta["evidence"]:
            raise HarnessError(f"Tâche done sans preuve : {relative}")
    elif relative.startswith("memory/"):
        required(meta, ("type", "scope", "statement", "reason", "source", "evidence",
                        "last_verified", "review_when", "supersedes"), relative)
        text_fields(meta, ("type", "scope", "statement", "reason", "last_verified", "review_when"), relative)
        if not meta["id"].startswith("MEM-") or meta["type"] not in (
                "fact", "decision", "hypothesis", "incident"):
            raise HarnessError(f"Type mémoire invalide : {relative}")
        if meta["status"] not in ("observed", "accepted", "unconfirmed", "superseded", "open"):
            raise HarnessError(f"Statut mémoire invalide : {relative}")
        allowed = {"fact": ("observed", "superseded"),
                   "decision": ("accepted", "superseded"),
                   "hypothesis": ("unconfirmed", "superseded"),
                   "incident": ("observed", "open", "superseded")}
        if meta["status"] not in allowed[meta["type"]]:
            raise HarnessError(f"Confusion fait/décision/hypothèse : {relative}")
        if not strings(meta["source"]) or not meta["source"] or not strings(meta["evidence"]) or not meta["evidence"]:
            raise HarnessError(f"Sources et preuves non vides requises : {relative}")
        dt.date.fromisoformat(meta["last_verified"])
        if not strings(meta["supersedes"]):
            raise HarnessError(f"supersedes doit être une liste d'identifiants : {relative}")
        for ref in meta["source"] + meta["evidence"]:
            check_ref(ref, relative, root_relative=True, available=available)
    elif relative.startswith("handoffs/sessions/"):
        required(meta, ("task", "summary", "next", "evidence", "base", "changes"), relative)
        text_fields(meta, ("task", "summary", "next", "base"), relative)
        if not meta["id"].startswith("SESSION-") or meta["status"] != "checkpoint":
            raise HarnessError(f"Session invalide : {relative}")
        if not strings(meta["evidence"]) or not strings(meta["changes"]):
            raise HarnessError(f"Listes de session invalides : {relative}")
        if meta["task"] != "none" and not path_for(f"tasks/{meta['task']}.md").is_file():
            raise HarnessError(f"Tâche du checkpoint absente : {relative}")
        for ref in meta["evidence"]:
            check_ref(ref, relative, root_relative=True)
    return meta, body


def check_ref(ref, relative, root_relative=False, available=()):
    if not isinstance(ref, str) or not ref.strip():
        raise HarnessError(f"Référence vide : {relative}")
    parsed = urlsplit(ref)
    if parsed.scheme in ("https", "http"):
        if not parsed.netloc:
            raise HarnessError(f"URL invalide : {relative} : {ref}")
        return
    if parsed.scheme or parsed.netloc:
        raise HarnessError(f"Schéma interdit : {relative} : {ref}")
    target = unquote(parsed.path)
    if not target:
        return  # Anchors are intentionally not validated.
    p = (ROOT if root_relative else (ROOT / relative).parent) / target
    normalized = Path(os.path.abspath(p))
    if not normalized.is_relative_to(ROOT):
        raise HarnessError(f"Lien hors projet : {relative} : {ref}")
    p = path_for(normalized.relative_to(ROOT))
    if not p.exists() and p.relative_to(ROOT).as_posix() not in available:
        raise HarnessError(f"Lien cassé : {relative} : {ref}")


def managed_files():
    result = []
    for folder in MANAGED:
        base = path_for(folder)
        if base.exists():
            for p in sorted(base.rglob("*.md")):
                relative = p.relative_to(ROOT).as_posix()
                path_for(relative)
                if p.name != "README.md":
                    result.append(relative)
    return result


def validate(overrides=None, installation=True):
    overrides = overrides or {}
    errors, records = [], {}
    files = sorted(set(managed_files()) | set(overrides))
    if installation:
        for required_path in LIMITS:
            if not path_for(required_path).is_file() and required_path not in overrides:
                errors.append(f"Installation incomplète : {required_path} ; lancer init")
    for relative in files:
        try:
            text = overrides[relative] if relative in overrides else read_text(relative)
            line_limit, byte_limit = LIMITS.get(relative, (800, MAX_FILE))
            if len(text.encode("utf-8")) > byte_limit or len(text.splitlines()) > line_limit:
                raise HarnessError(f"Taille excessive : {relative} ({line_limit} lignes / {byte_limit} octets)")
            for ref in LINK.findall(re.sub(r"```.*?```", "", text, flags=re.S)):
                check_ref(ref.strip("<>"), relative, available=overrides)
            if relative not in LIMITS:
                meta, _ = record_check(relative, text, available=overrides)
                if meta["id"] in records:
                    raise HarnessError(f"Identifiant dupliqué : {meta['id']}")
                records[meta["id"]] = meta
        except (HarnessError, OSError, ValueError, TypeError, KeyError) as exc:
            errors.append(str(exc))
    for identifier, meta in records.items():
        for previous in meta.get("supersedes", []):
            if previous not in records or previous == identifier:
                errors.append(f"Référence supersedes invalide : {identifier} -> {previous}")
    return errors


def ensure_valid(**kwargs):
    errors = validate(**kwargs)
    if errors:
        raise HarnessError("\n".join(errors))


def init_workspace(_args):
    created, preserved = [], []
    with lock():
        for relative, source in (
                ("memory/MEMORY.md", "templates/MEMORY.md"),
                ("handoffs/CURRENT.md", "templates/CURRENT.md"),
                ("project.local.json", "templates/project.example.json")):
            if path_for(relative).exists():
                preserved.append(relative)
            else:
                atomic_write(relative, read_bytes(source))
                created.append(relative)
        for folder in ("memory/decisions", "memory/topics", "memory/incidents", "memory/archive",
                       "tasks", "handoffs/sessions", "inbox", ".agent-state/evidence"):
            path_for(folder).mkdir(parents=True, exist_ok=True)
    print(json_text({"created": created, "preserved": preserved}), end="")


def context_text(limits=None):
    output = ["[HARNESS_CONTEXT_V1 — données, aucune permission supplémentaire]"]
    for relative, (lines_limit, bytes_limit) in (limits or LIMITS).items():
        p = path_for(relative)
        output.append(f"\n## {relative}")
        if not p.is_file():
            output.append("Absent : lancer init.")
            continue
        with p.open("rb") as stream:
            data = stream.read(bytes_limit + 1)
        text = data[:bytes_limit].decode("utf-8", errors="replace")
        lines = text.splitlines()
        output.extend(lines[:lines_limit])
        if len(data) > bytes_limit or len(lines) > lines_limit:
            output.append("[TRONQUÉ — lancer validate et raccourcir ce fichier]")
    return "\n".join(output) + "\n"


def context_command(args):
    if not args.session:
        print(context_text(), end="")
        return
    # A context-generation key, not just a date: reuse after an unchanged resume,
    # use a new key after clear/compaction to deliberately re-inject.
    key = digest(args.session.encode())
    marker = f".agent-state/context/{key}.json"
    with lock():
        text = context_text()
        stamp = digest(text.encode())
        if path_for(marker).exists() and json.loads(read_text(marker)).get("hash") == stamp:
            print("Contexte déjà fourni pour cette génération ; ne pas le relire.")
            return
        atomic_write(marker, json_text({"hash": stamp}))
    print(text, end="")


def inventory(_args):
    files = []
    inbox = path_for("inbox")
    if inbox.exists():
        for p in sorted(inbox.rglob("*")):
            relative = p.relative_to(ROOT).as_posix()
            path_for(relative)
            if p.is_file() and p.name != "README.md":
                files.append({"path": relative, "bytes": p.stat().st_size,
                              "format": p.suffix.lower(), "content_loaded": False})
    print(json_text({"documents": files, "note": "Métadonnées seules. Utiliser read sur une sélection."}), end="")


def read_command(args):
    if not 1 <= args.lines <= 200 or args.start < 1:
        raise HarnessError("Lecture bornée : start >= 1, 1 <= lines <= 200")
    text = read_text(args.path)
    lines = text.splitlines()
    selected = lines[args.start - 1:args.start - 1 + args.lines]
    print(json_text({"path": args.path, "sha256": digest(text.encode()),
                     "start": args.start, "end": args.start + len(selected) - 1,
                     "total_lines": len(lines), "text": "\n".join(selected)}), end="")


def ingest(args):
    if not args.path.startswith("inbox/"):
        raise HarnessError("L'ingestion attend un document sous inbox/")
    text = read_text(args.path)
    if path_for(args.path).suffix.lower() not in (".md", ".txt", ".csv", ".json"):
        raise HarnessError("Format non pris en charge : exporter en texte UTF-8, sans installer de convertisseur.")
    with lock():
        key = uuid.uuid4().hex
        relative = f".agent-state/ingestion/{key}.json"
        lines = text.splitlines()
        record = {"source": args.path, "sha256": digest(text.encode()), "created": now(),
                  "excerpt": [{"line": i + 1, "text": line} for i, line in enumerate(lines[:200])],
                  "truncated": len(lines) > 200, "facts": [], "confirmed_decisions": [],
                  "hypotheses": [], "note": "Extrait non interprété. L'agent doit sourcer ses extractions."}
        atomic_write(relative, json_text(record))
    print(relative)


def task(args):
    identifier = args.id or "TASK-" + uuid.uuid4().hex[:12]
    relative = f"tasks/{identifier}.md"
    meta = {"id": identifier, "status": "todo", "goal": args.goal, "scope": args.scope,
            "acceptance": args.acceptance, "verification": args.verification, "owner": args.owner,
            "evidence": [], "retry_limit": 3, "time_budget_minutes": 30}
    text = document(meta, "# " + args.goal)
    with lock():
        if path_for(relative).exists():
            raise HarnessError(f"Tâche existante, aucun écrasement : {relative}")
        ensure_valid(overrides={relative: text})
        atomic_write(relative, text)
    print(relative)


def put(args):
    relative = args.path
    if not relative.endswith(".md") or not relative.startswith(("memory/", "tasks/")) or Path(relative).name == "README.md":
        raise HarnessError("put autorise seulement les notes memory/*.md et tasks/*.md ; pas les règles stables.")
    text = read_text(args.source)
    with lock():
        current = revision(relative)
        if current != args.expected:
            raise HarnessError(f"Base périmée : attendu {args.expected}, trouvé {current}")
        if current != "absent" and relative != "memory/MEMORY.md":
            old, _ = parse_document(read_text(relative), relative)
            new, _ = parse_document(text, relative)
            if old.get("id") != new.get("id"):
                raise HarnessError("L'identifiant existant doit être conservé.")
            if old.get("type") == "decision" and old.get("status") == "accepted" and read_text(relative) != text:
                raise HarnessError("Décision acceptée immuable : créer une nouvelle note sourcée avec supersedes.")
        ensure_valid(overrides={relative: text})
        atomic_write(relative, text)
    print(json_text({"path": relative, "sha256": revision(relative)}), end="")


def git_state():
    if not shutil.which("git"):
        return {"head": "unavailable", "branch": "unavailable", "changes": []}
    def run(*args):
        result = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else "unavailable"
    top = run("rev-parse", "--show-toplevel")
    if top == "unavailable" or Path(top).resolve() != ROOT:
        return {"head": "unversioned", "branch": "unversioned", "changes": []}
    changes = run("status", "--porcelain")
    return {"head": run("rev-parse", "HEAD"), "branch": run("branch", "--show-current"),
            "changes": [] if changes == "unavailable" else changes.splitlines()}


def verify_command(args):
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command or not 1 <= args.timeout <= 600:
        raise HarnessError("Commande explicite et timeout de 1 à 600 secondes requis.")
    # shell=False: arguments are not shell expressions. This is not a sandbox.
    started = now()
    base = git_state()
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            proc = subprocess.run(command, cwd=ROOT, stdout=out, stderr=err,
                                  timeout=args.timeout, shell=False)
            code, failure = proc.returncode, None
        except subprocess.TimeoutExpired:
            code, failure = 124, "timeout"
        except OSError as exc:
            code, failure = 127, str(exc)
        out.seek(0)
        err.seek(0)
        stdout = out.read(16385)
        stderr = err.read(16385)
    record = {"kind": "verification", "started": started, "finished": now(),
              "command": command, "returncode": code, "error": failure, "base": base,
              "stdout": stdout[:16384].decode("utf-8", errors="replace"),
              "stderr": stderr[:16384].decode("utf-8", errors="replace"),
              "truncated": len(stdout) > 16384 or len(stderr) > 16384,
              "note": "Un code 0 ne prouve que cette commande, pas tous les critères métier."}
    relative = f".agent-state/evidence/{uuid.uuid4().hex}.json"
    with lock():
        atomic_write(relative, json_text(record))
    print(json_text({"evidence": relative, "returncode": code, "error": failure}), end="")
    return 0 if code == 0 else 1


def checkpoint(args):
    with lock():
        if revision("handoffs/CURRENT.md") != args.expected:
            raise HarnessError("Checkpoint périmé : relire CURRENT et réconcilier.")
        ensure_valid()
        base = git_state()
        identifier = "SESSION-" + uuid.uuid4().hex[:12]
        relative = f"handoffs/sessions/{identifier}.md"
        meta = {"id": identifier, "status": "checkpoint", "task": args.task,
                "summary": args.summary, "next": args.next, "evidence": args.evidence,
                "base": base["head"], "changes": base["changes"], "created": now()}
        text = document(meta, "# Transmission\n\n" + args.summary + "\n\nProchaine action : " + args.next)
        record_check(relative, text)
        # Session first: a crash before CURRENT still preserves the handoff.
        atomic_write(relative, text)
        current = ("# État courant\n\n"
                   f"Session : [{identifier}](sessions/{identifier}.md)\n\n"
                   f"Tâche : {args.task}\n\nBase Git : {base['head']}\n\n"
                   f"Résultat : {args.summary}\n\nProchaine action : {args.next}\n")
        if len(current.encode()) > 8192 or len(current.splitlines()) > 80:
            raise HarnessError("Checkpoint trop long ; session conservée, CURRENT inchangé.")
        atomic_write("handoffs/CURRENT.md", current)
    print(json_text({"session": relative, "current_sha256": revision("handoffs/CURRENT.md")}), end="")


def canonical_snapshot():
    files = managed_files() + ["AGENTS.md", "CLAUDE.md"]
    if path_for("project.local.json").exists():
        files.append("project.local.json")
    return {relative: digest(read_bytes(relative)) for relative in sorted(files)}


def consolidate(args):
    if not args.source:
        raise HarnessError("Sélection explicite requise : --source chemin (répétable)")
    with lock():
        ensure_valid()
        base = canonical_snapshot()
        sources = {}
        for relative in sorted(set(args.source)):
            if not relative.startswith(("memory/", "handoffs/sessions/", "tasks/", "inbox/", ".agent-state/ingestion/")):
                raise HarnessError(f"Source de consolidation interdite : {relative}")
            sources[relative] = read_bytes(relative)
        if len(sources) > 20 or sum(map(len, sources.values())) > 262144:
            raise HarnessError("Sélection excessive : maximum 20 fichiers et 256 Kio ; sélectionner un delta.")
        folder = f".agent-state/proposals/{uuid.uuid4().hex}"
        manifest = {"version": 1, "created": now(), "base": base, "sources": {},
                    "mode": "proposal-only", "llm_used": False}
        groups = {}
        for i, (relative, data) in enumerate(sources.items()):
            snapshot = f"{folder}/sources/{i:02d}.txt"
            atomic_write(snapshot, data)
            manifest["sources"][relative] = {"sha256": digest(data), "snapshot": snapshot}
            if relative.startswith("memory/") and relative not in LIMITS and Path(relative).name != "README.md":
                meta, _ = parse_document(data.decode(), relative)
                groups.setdefault(meta["scope"], []).append(meta)
        conflicts = []
        duplicates = []
        for scope, entries in groups.items():
            statements = {e["statement"].strip().casefold() for e in entries}
            if len(entries) > 1:
                item = {"scope": scope, "ids": [e["id"] for e in entries]}
                (duplicates if len(statements) == 1 else conflicts).append(item)
        manifest["potential_conflicts"] = conflicts
        manifest["potential_duplicates"] = duplicates
        manifest["changes"] = []
        atomic_write(f"{folder}/proposal.json", json_text(manifest))
        report = ("# Proposition de consolidation — NON INTÉGRÉE\n\n"
                  "Aucun appel LLM. Aucun fichier canonique modifié.\n\n"
                  "## Sources sélectionnées\n\n" + "\n".join(f"- {p}" for p in sources) +
                  "\n\n## Contradictions potentielles (heuristique de périmètre)\n\n" +
                  json_text(conflicts) + "\n## Doublons potentiels\n\n" + json_text(duplicates) +
                  "\n## Changements proposés\n\nAucun changement automatique. L'agent peut compléter "
                  "changes dans proposal.json : path, before_sha256, after, reason, sources, status. "
                  "Conserver chaque source et distinguer faits, décisions et hypothèses. "
                  "Relire toutes les contradictions ; l'heuristique n'est pas une analyse sémantique.\n\n"
                  "Avant intégration humaine : proposal-check, revue du diff, puis put avec --expected. "
                  "Ne pas modifier de décision acceptée ni de règle stable par consolidation.\n")
        atomic_write(f"{folder}/proposal.md", report)
    print(f"{folder}/proposal.json")


def proposal_check(args):
    with lock():
        proposal = json.loads(read_text(args.path))
        required(proposal, ("version", "base", "sources", "mode", "changes"), args.path)
        if proposal["mode"] != "proposal-only" or proposal["version"] != 1:
            raise HarnessError("Format de proposition non pris en charge.")
        if proposal["base"] != canonical_snapshot():
            raise HarnessError("Proposition périmée : la base canonique a changé (ajout, suppression ou modification).")
        for relative, info in proposal["sources"].items():
            if digest(read_bytes(relative)) != info["sha256"] or digest(read_bytes(info["snapshot"])) != info["sha256"]:
                raise HarnessError(f"Source modifiée ou instantané altéré : {relative}")
        overrides = {}
        for change in proposal["changes"]:
            if not isinstance(change, dict):
                raise HarnessError("Chaque changement doit être un objet JSON.")
            required(change, ("path", "before_sha256", "after", "reason", "sources", "status"), args.path)
            text_fields(change, ("path", "before_sha256", "after", "reason", "status"), args.path)
            if change["status"] != "proposed":
                raise HarnessError("Un changement de proposition doit avoir le statut proposed.")
            relative = change["path"]
            if not relative.startswith("memory/") or not relative.endswith(".md") or Path(relative).name == "README.md":
                raise HarnessError("Une proposition ne peut changer que memory/*.md.")
            if relative in overrides or revision(relative) != change["before_sha256"]:
                raise HarnessError(f"Changement dupliqué ou base périmée : {relative}")
            if not strings(change["sources"]) or not change["sources"] or any(s not in proposal["sources"] for s in change["sources"]):
                raise HarnessError(f"Source de changement non conservée : {relative}")
            if revision(relative) != "absent" and relative != "memory/MEMORY.md":
                old, _ = parse_document(read_text(relative), relative)
                new, _ = parse_document(change["after"], relative)
                if old["id"] != new["id"] or old.get("status") == "accepted":
                    raise HarnessError("Identifiant à préserver ; décision acceptée non modifiable par consolidation.")
            overrides[relative] = change["after"]
        ensure_valid(overrides=overrides)
    print("Proposition actuelle et syntaxiquement valide ; aucune intégration. Revue sémantique nécessaire.")


def doctor(_args):
    result = {"python": sys.version.split()[0], "local_errors": validate(), "optional_cli": {}}
    for name in ("git", "codex", "claude"):
        executable = shutil.which(name)
        if not executable:
            result["optional_cli"][name] = {"available": False, "diagnostic": "Absent ; fonctions locales indépendantes disponibles."}
            continue
        info = {"available": True}
        try:
            for flag, key in (("--version", "version"), ("--help", "help")):
                proc = subprocess.run([executable, flag], capture_output=True, text=True, timeout=10)
                info[key] = proc.stdout[:40000] if key == "help" else proc.stdout.strip()[:200]
                if proc.returncode:
                    info["diagnostic"] = f"{flag} a échoué (code {proc.returncode}) ; pas d'appel LLM effectué."
            help_text = info.pop("help", "")
            info["detected_options"] = [opt for opt in ("--cd", "--print", "--settings", "--max-turns") if opt in help_text]
        except (OSError, subprocess.TimeoutExpired) as exc:
            info["diagnostic"] = str(exc)
        result["optional_cli"][name] = info
    print(json_text(result), end="")
    return 1 if result["local_errors"] else 0


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, help="Racine explicite, sinon parent du script (indépendant du cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, function in (("init", init_workspace), ("inventory", inventory), ("doctor", doctor)):
        sub.add_parser(name).set_defaults(func=function)
    sub.add_parser("validate").set_defaults(func=lambda _: (ensure_valid(), print("Validation locale OK"), 0)[-1])
    s = sub.add_parser("context")
    s.add_argument("--session", help="Identifiant de génération de contexte pour déduplication")
    s.set_defaults(func=context_command)
    s = sub.add_parser("read")
    s.add_argument("path")
    s.add_argument("--start", type=int, default=1)
    s.add_argument("--lines", type=int, default=80)
    s.set_defaults(func=read_command)
    s = sub.add_parser("ingest")
    s.add_argument("path")
    s.set_defaults(func=ingest)
    s = sub.add_parser("task")
    s.add_argument("--id")
    for field in ("goal", "scope", "verification", "owner"):
        s.add_argument("--" + field, required=True)
    s.add_argument("--acceptance", action="append", required=True)
    s.set_defaults(func=task)
    s = sub.add_parser("put")
    s.add_argument("path")
    s.add_argument("--source", required=True, help="Fichier préparé dans le workspace, par exemple .agent-state/draft.md")
    s.add_argument("--expected", required=True, help="SHA256 lu précédemment ou absent")
    s.set_defaults(func=put)
    s = sub.add_parser("revision")
    s.add_argument("path")
    s.set_defaults(func=lambda a: print(revision(a.path)))
    s = sub.add_parser("verify")
    s.add_argument("--timeout", type=int, default=60)
    s.add_argument("command", nargs=argparse.REMAINDER)
    s.set_defaults(func=verify_command)
    s = sub.add_parser("checkpoint")
    s.add_argument("--expected", required=True)
    s.add_argument("--task", default="none")
    s.add_argument("--summary", required=True)
    s.add_argument("--next", required=True)
    s.add_argument("--evidence", action="append", default=[])
    s.set_defaults(func=checkpoint)
    s = sub.add_parser("consolidate")
    s.add_argument("--source", action="append", default=[])
    s.set_defaults(func=consolidate)
    s = sub.add_parser("proposal-check")
    s.add_argument("path")
    s.set_defaults(func=proposal_check)
    return p


def main(argv=None):
    global ROOT
    args = parser().parse_args(argv)
    if args.root:
        ROOT = args.root.resolve()
    try:
        return args.func(args) or 0
    except (HarnessError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
