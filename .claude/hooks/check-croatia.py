#!/usr/bin/env python3
"""Contrôle « Croatie inchangée » (règle 3 de CLAUDE.md), déterministe.

Compare les données Croatie d'index.html (copie de travail) avec celles de main,
valeur par valeur : chaque donnée est lue, convertie en valeur (JSON), puis
comparée par empreinte SHA-256. Affiche PASS ou FAIL en français, avec la donnée
qui diffère et le premier chemin en écart.

Données contrôlées : DATA, ISLAND_POLYGONS, ISLAND_LABELS, ISLAND_LABEL_POS,
ISLAND_NAME_POS, DEFAULT_ROUTE_WAYPOINTS, ARCHIVE_ETE_2026, et les paramètres
du profil AREAS.croatia (title, baseStop, seaGrid, checkpointSeq…).
Le comportement (planificateur, vent, cartes) reste vérifié par l'agent croatia-guardian.

Deux usages :
- Hook Stop (sans argument) : ne fait rien si index.html est identique à main ;
  sinon contrôle, et en cas d'écart sort avec le code 2 (arrêt bloqué, à corriger).
- À la main : check-croatia.py [--fichier CHEMIN] [--ref main]  (contrôle toujours fait).
Codes de sortie : 0 = PASS (ou rien à contrôler), 2 = FAIL.
Utilise seulement python3 et git, déjà présents sur macOS.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

NOMS = ['DATA', 'ISLAND_POLYGONS', 'ISLAND_LABELS', 'ISLAND_LABEL_POS',
        'ISLAND_NAME_POS', 'DEFAULT_ROUTE_WAYPOINTS', 'ARCHIVE_ETE_2026']


# ---------- lecture des littéraux JavaScript ----------

def fin_litteral(texte, debut):
    """Index juste après le {…} ou […] qui commence à `debut` (chaînes et commentaires sautés)."""
    pile, i, n = [], debut, len(texte)
    while i < n:
        c = texte[i]
        if c in '"\'`':
            i += 1
            while i < n and texte[i] != c:
                i += 2 if texte[i] == '\\' else 1
        elif texte.startswith('//', i):
            i = texte.find('\n', i)
            if i < 0:
                return n
            continue
        elif c in '{[(':
            pile.append(c)
        elif c in '}])':
            pile.pop()
            if not pile:
                return i + 1
        i += 1
    raise ValueError('littéral non fermé')


def litteral(texte, nom):
    """Texte du littéral affecté par `const <nom> = {…}` ou `[…]` (première occurrence)."""
    m = re.search(r'^\s*const ' + re.escape(nom) + r'\s*=\s*([\[{])', texte, re.M)
    if not m:
        return None
    debut = m.start(1)
    return texte[debut:fin_litteral(texte, debut)]


def js_vers_valeur(code):
    """Convertit un littéral JS simple en valeur Python ; repli sur le texte normalisé
    (sans commentaires ni espaces hors chaînes) s'il contient du code (fonctions…)."""
    morceaux, i, n = [], 0, len(code)
    while i < n:
        c = code[i]
        if c in '"\'':
            j = i + 1
            while code[j] != c:
                j += 2 if code[j] == '\\' else 1
            contenu = code[i + 1:j]
            if c == "'":
                contenu = contenu.replace("\\'", "'").replace('"', '\\"')
            morceaux.append(('chaine', '"' + contenu + '"'))
            i = j + 1
        elif code.startswith('//', i):
            j = code.find('\n', i)
            i = n if j < 0 else j
        else:
            j = i
            while j < n and code[j] not in '"\'' and not code.startswith('//', j):
                j += 1
            frag = re.sub(r'\s+', '', code[i:j])
            if morceaux and morceaux[-1][0] == 'code':  # fusion autour d'un commentaire retiré
                morceaux[-1] = ('code', morceaux[-1][1] + frag)
            else:
                morceaux.append(('code', frag))
            i = j
    texte = ''.join(m for _, m in morceaux)
    json_txt = ''.join(re.sub(r'([{,])([A-Za-z_]\w*):', r'\1"\2":', m) if t == 'code' else m
                       for t, m in morceaux)
    json_txt = re.sub(r',([}\]])', r'\1', json_txt)
    try:
        return json.loads(json_txt)
    except ValueError:
        return {'texte normalisé': texte}


def profil_croatie(texte):
    """Paramètres du profil : objet `return {…}` de l'IIFE AREAS.croatia, sans les données."""
    m = re.search(r'^AREAS\.croatia\s*=\s*\(\(\)\s*=>\s*\{', texte, re.M)
    if not m:
        return None
    bloc = texte[m.end() - 1:fin_litteral(texte, m.end() - 1)]
    r = re.search(r'\breturn\s*\{', bloc)
    if not r:
        return None
    obj = bloc[r.end() - 1:fin_litteral(bloc, r.end() - 1)]
    # retire les entrées qui renvoient aux données (contrôlées à part) : `DATA, …` et `archive: ARCHIVE_ETE_2026`
    obj = re.sub(r'archive\s*:\s*ARCHIVE_ETE_2026', '', obj)
    for nom in NOMS:
        obj = re.sub(r'(?<![\w.\'"])' + nom + r'(?![\w\'"])\s*,?', '', obj)
    return js_vers_valeur(obj)


def donnees(texte):
    res = {nom: (js_vers_valeur(t) if (t := litteral(texte, nom)) is not None else None) for nom in NOMS}
    res['paramètres du profil AREAS.croatia'] = profil_croatie(texte)
    return res


# ---------- comparaison ----------

def empreinte(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()[:12]


def ecarts(a, b, chemin='', out=None, limite=5):
    out = [] if out is None else out
    if len(out) >= limite:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a:
                out.append(f'{chemin}.{k} : ajouté ({json.dumps(b[k], ensure_ascii=False)[:80]})')
            elif k not in b:
                out.append(f'{chemin}.{k} : supprimé')
            else:
                ecarts(a[k], b[k], f'{chemin}.{k}', out, limite)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f'{chemin} : {len(a)} éléments sur main, {len(b)} ici')
        for i, (x, y) in enumerate(zip(a, b)):
            ecarts(x, y, f'{chemin}[{i}]', out, limite)
    elif a != b:
        f = lambda v: json.dumps(v, ensure_ascii=False)[:80]
        out.append(f'{chemin or "(valeur)"} : main = {f(a)} → ici = {f(b)}')
    return out[:limite]


# ---------- programme ----------

def git(racine, *args):
    return subprocess.run(['git', '-C', racine, *args], capture_output=True, text=True)


def main():
    p = argparse.ArgumentParser(description='Contrôle Croatie inchangée (données) par rapport à main.')
    p.add_argument('--fichier', help="index.html à contrôler (défaut : celui du dépôt)")
    p.add_argument('--ref', default='main', help='référence git (défaut : main)')
    args = p.parse_args()
    mode_hook = args.fichier is None
    racine = os.environ.get('CLAUDE_PROJECT_DIR') or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    fichier = args.fichier or os.path.join(racine, 'index.html')

    # Référence : main, sinon origin/main (clone sans branche main locale)
    candidats = [args.ref] + ([f'origin/{args.ref}'] if '/' not in args.ref else [])
    args.ref = next((r for r in candidats if git(racine, 'rev-parse', '--verify', '-q', r + '^{commit}').returncode == 0), None)
    if args.ref is None:
        print(f"Contrôle Croatie : référence {' / '.join(candidats)} introuvable, contrôle non fait.", file=sys.stderr)
        return 0 if mode_hook else 2  # en hook, ne bloque pas l'arrêt indéfiniment

    if mode_hook:
        try:
            sys.stdin.read()  # entrée JSON du hook Stop, non utilisée
        except Exception:
            pass
        # Rien à contrôler si index.html est identique à main (commits et copie de travail compris)
        if git(racine, 'diff', '--quiet', args.ref, '--', 'index.html').returncode == 0:
            return 0

    ref = git(racine, 'show', f'{args.ref}:index.html')
    if ref.returncode != 0:
        print(f"Contrôle Croatie : impossible de lire {args.ref}:index.html ({ref.stderr.strip()}).", file=sys.stderr)
        return 2
    a, b = donnees(ref.stdout), donnees(open(fichier, encoding='utf-8').read())

    lignes, ok = [], True
    for nom in a:
        va, vb = a[nom], b[nom]
        if va is None:
            lignes.append(f'  ? {nom} : absent de {args.ref} (non contrôlé)')
            continue
        if vb is None:
            ok = False
            lignes.append(f'  ✗ {nom} : introuvable dans {fichier}')
            continue
        ea, eb = empreinte(va), empreinte(vb)
        if ea == eb:
            lignes.append(f'  ✓ {nom} : identique (empreinte {ea})')
        else:
            ok = False
            lignes.append(f'  ✗ {nom} : DIFFÉRENT (empreinte {args.ref} {ea} ≠ ici {eb})')
            lignes += [f'      - {e}' for e in ecarts(va, vb)]

    titre = f'Contrôle Croatie (données, comparées à {args.ref}) : ' + ('PASS' if ok else 'FAIL')
    rapport = '\n'.join([titre] + lignes)
    if ok:
        print(rapport)
        return 0
    print(rapport + "\n⛔ Données Croatie modifiées (règle 3) : corrige l'écart ci-dessus avant de t'arrêter.",
          file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
