#!/usr/bin/env python3
"""Hook PreToolUse « jamais sur main » (règle 1 de CLAUDE.md).

Bloque (exit 2) :
- tout `git commit` quand la branche courante est main ;
- tout `git push` qui vise main (push depuis main sans refspec,
  `origin main`, `HEAD:main`, `+main`, `:main`, --all, --mirror, force push…).
Tout le reste passe (exit 0), y compris le push d'une branche de travail.
Utilise seulement python3 et git, déjà présents sur macOS.
"""
import json
import os
import shlex
import subprocess
import sys

PROTECTED = "main"
SEPARATORS = {"&&", "||", ";", "|", "&", "(", ")"}
# Options globales de git qui prennent une valeur dans l'argument suivant.
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
# Options de git push qui prennent une valeur dans l'argument suivant.
PUSH_OPTS_WITH_VALUE = {"--repo", "-o", "--push-option", "--receive-pack", "--exec"}


def block(message):
    sys.stderr.write("⛔ Bloqué par le hook « jamais sur main » : " + message + "\n"
                     "Crée une branche (feat/…, fix/…, chore/…) et travaille dessus. "
                     "C'est l'utilisateur qui fusionne dans main sur GitHub.\n")
    sys.exit(2)


def current_branch(cwd):
    try:
        out = subprocess.run(["git", "-C", cwd, "symbolic-ref", "--short", "-q", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip()
    except Exception:
        return ""


def segments(command):
    """Découpe la commande en sous-commandes (&&, ;, |, …)."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:  # guillemets non fermés : on découpe grossièrement
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
        opt = seg[i]
        if opt in GIT_OPTS_WITH_VALUE and i + 1 < len(seg):
            if opt == "-C":
                repo = os.path.join(repo, seg[i + 1])
            i += 2
        else:
            i += 1
    if i >= len(seg):
        return None
    return seg[i], seg[i + 1:], repo


def push_targets_main(args, branch):
    positional = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--all", "--mirror"):
            return True  # poussent toutes les branches, main compris
        if a in PUSH_OPTS_WITH_VALUE:
            i += 2
            continue
        if not a.startswith("-"):
            positional.append(a)
        i += 1
    refspecs = positional[1:]  # le premier positionnel est le remote
    if not refspecs:
        return branch == PROTECTED  # push de la branche courante
    for spec in refspecs:
        spec = spec.lstrip("+")
        dst = spec.split(":", 1)[1] if ":" in spec else spec
        if dst == "HEAD":
            dst = branch  # `git push origin HEAD` pousse la branche courante
        dst = dst.replace("refs/heads/", "", 1)
        if dst == PROTECTED:
            return True
    return False


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    command = (data.get("tool_input") or {}).get("command", "")
    cwd = data.get("cwd") or os.getcwd()
    for seg in segments(command):
        parsed = parse_git(seg, cwd)
        if not parsed:
            continue
        sub, args, repo = parsed
        branch = current_branch(repo)
        if sub == "commit" and branch == PROTECTED:
            block("commit interdit sur la branche main.")
        if sub == "push" and push_targets_main(args, branch):
            block("push vers main interdit (« " + " ".join(seg) + " »).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
