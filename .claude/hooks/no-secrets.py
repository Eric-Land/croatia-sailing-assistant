#!/usr/bin/env python3
"""Hook PreToolUse « pas de secrets » (règle 6 de CLAUDE.md).

Avant tout `git commit`, analyse les lignes ajoutées dans l'index
(et, si la commande contient `git add` ou `commit -a`, les modifications
non indexées et les fichiers non suivis). Bloque (exit 2) si une ligne
ressemble à un secret : jeton GitHub, clé d'API, clé privée,
affectation password=/token= avec une valeur littérale.
Le message donne le fichier et la ligne, jamais le secret lui-même.
Utilise seulement python3 et git, déjà présents sur macOS.
"""
import json
import os
import re
import shlex
import subprocess
import sys

PATTERNS = [
    ("jeton GitHub", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b")),
    ("jeton GitHub", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}")),
    ("clé d'API (sk-)", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("clé d'accès AWS", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("clé privée", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    # Affectation avec une valeur littérale entre guillemets : password = "…"
    ("mot de passe ou jeton en clair", re.compile(
        r"(?i)\b(password|passwd|pwd|secret|token|api_?key)\w*\s*[:=]\s*['\"][^'\"\s]{6,}['\"]")),
    # Affectation de type .env en début de ligne : TOKEN=…
    ("mot de passe ou jeton en clair", re.compile(
        r"(?i)^\s*(export\s+)?\w*(password|passwd|secret|token|api_?key)\w*=[^\s'\"$]{6,}")),
]
SEPARATORS = {"&&", "||", ";", "|", "&", "(", ")"}
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
MAX_FILE_BYTES = 1_000_000


def segments(command):
    """Découpe la commande en sous-commandes (&&, ;, |, …)."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        tokens = command.split()
    seg = []
    for tok in tokens:
        if tok in SEPARATORS:
            if seg:
                yield seg
            seg = []
        else:
            seg.append(tok)
    if seg:
        yield seg


def parse_git(seg, cwd):
    """Renvoie (sous-commande, arguments, dossier du dépôt) ou None."""
    if "git" not in seg:
        return None
    i = seg.index("git") + 1
    repo = cwd
    while i < len(seg) and seg[i].startswith("-"):
        if seg[i] in GIT_OPTS_WITH_VALUE and i + 1 < len(seg):
            if seg[i] == "-C":
                repo = os.path.join(repo, seg[i + 1])
            i += 2
        else:
            i += 1
    if i >= len(seg):
        return None
    return seg[i], seg[i + 1:], repo


def git(repo, *args):
    out = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                         errors="replace", timeout=20)
    return out.stdout if out.returncode == 0 else ""


def added_lines(diff):
    """Lignes ajoutées d'un diff -U0 : (fichier, numéro de ligne, texte)."""
    path, line_no = None, 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            path = raw[6:] if raw.startswith("+++ b/") else None
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            line_no = int(m.group(1)) if m else 0
        elif raw.startswith("+") and path:
            yield path, line_no, raw[1:]
            line_no += 1


def untracked_lines(repo):
    for rel in git(repo, "ls-files", "--others", "--exclude-standard").splitlines():
        full = os.path.join(repo, rel)
        try:
            if os.path.getsize(full) > MAX_FILE_BYTES:
                continue
            with open(full, encoding="utf-8", errors="strict") as f:
                for n, text in enumerate(f, 1):
                    yield rel, n, text.rstrip("\n")
        except (OSError, UnicodeDecodeError):
            continue  # fichier binaire ou illisible


def find_secret(lines):
    for path, n, text in lines:
        for label, rx in PATTERNS:
            if rx.search(text):
                return path, n, label
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    command = (data.get("tool_input") or {}).get("command", "")
    cwd = data.get("cwd") or os.getcwd()
    adds_before = False  # un `git add` précède le commit dans la même commande
    for seg in segments(command):
        parsed = parse_git(seg, cwd)
        if not parsed:
            continue
        sub, args, repo = parsed
        if sub == "add":
            adds_before = True
            continue
        if sub != "commit":
            continue
        all_flag = "--all" in args or any(
            a.startswith("-") and not a.startswith("--") and "a" in a for a in args)
        sources = [added_lines(git(repo, "diff", "--cached", "-U0", "--no-color", "--no-ext-diff"))]
        if all_flag or adds_before:
            sources.append(added_lines(git(repo, "diff", "-U0", "--no-color", "--no-ext-diff")))
        if adds_before:
            sources.append(untracked_lines(repo))
        for lines in sources:
            hit = find_secret(lines)
            if hit:
                path, n, label = hit
                sys.stderr.write(
                    "⛔ Bloqué par le hook « pas de secrets » : %s probable dans %s, ligne %d.\n"
                    "Retire la valeur du fichier (le dépôt est public). Pour un service qui exige "
                    "une clé, demande à l'utilisateur ; ne la mets jamais dans le dépôt.\n"
                    % (label, path, n))
                sys.exit(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
