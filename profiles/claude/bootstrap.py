#!/usr/bin/env python3
"""Optional SessionStart hook. No subprocess, no Stop, no paid calls."""
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid


def main():
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "scripts"))
    import harness
    harness.ROOT = root
    try:
        raw = sys.stdin.buffer.read(32769)
        if len(raw) > 32768:
            raise ValueError("événement trop volumineux")
        event = json.loads(raw)
        if not isinstance(event, dict) or event.get("hook_event_name") != "SessionStart":
            raise ValueError("événement SessionStart requis")
        sid, source = event.get("session_id"), event.get("source")
        if not isinstance(sid, str) or not sid or source not in ("startup", "resume", "clear", "compact"):
            raise ValueError("session_id et source de démarrage valides requis")
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
        if project_dir and Path(project_dir).resolve() != root:
            raise ValueError("le hook et CLAUDE_PROJECT_DIR désignent deux workspaces différents")
        stamp = ""
        transcript = event.get("transcript_path")
        if transcript:
            try:
                stat = Path(transcript).stat()
                stamp = f"{stat.st_size}:{stat.st_mtime_ns}"
            except OSError:
                pass
        if source in ("clear", "compact") and not stamp:
            stamp = uuid.uuid4().hex
        generation = hashlib.sha256(f"{source}:{stamp}".encode()).hexdigest()
        relative = f".agent-state/hooks/{hashlib.sha256(sid.encode()).hexdigest()}.json"
        # Keep the whole additionalContext below the current documented 10k
        # character inlining threshold, with room for both files and diagnostics.
        text = harness.context_text(limits={name: (40, 4000) for name in harness.LIMITS})
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        with harness.lock():
            if harness.path_for(relative).exists():
                previous = json.loads(harness.read_text(relative))
                same_generation = source in ("startup", "resume") or previous.get("generation") == generation
                if previous.get("hash") == content_hash and same_generation:
                    return 0
            harness.atomic_write(relative, harness.json_text({"hash": content_hash, "generation": generation}))
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "SessionStart", "additionalContext": text
        }}, ensure_ascii=False))
    except (harness.HarnessError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"HARNESS hook : {exc}. Exécuter harness.py context manuellement.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
