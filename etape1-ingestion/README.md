# Étape 1 — Choix du domaine et pipeline d'ingestion

## 1. Collection de documents

- **Source** : dépôt open-source [astral-sh/uv](https://github.com/astral-sh/uv), dossier `docs/`, licence MIT / Apache-2.0.
- **Commit figé** : `d5c3f174417418c24ec3c276e01b0f62b961b13c`.
- **Sélection** : 55 fichiers Markdown. Les 81 fichiers de `docs/` dépassaient la fourchette 30–75, donc `docs/guides/` (26 fichiers) est exclu. Sous-dossiers conservés : `concepts/`, `getting-started/`, `pip/`, `reference/`, plus `index.md`.
- **Taille brute** : environ 377 000 caractères.

Reconstruction du corpus à partir du commit figé :

```bash
bash build_corpus.sh corpus
```

Le script clone uniquement ce commit (`--depth 1`), copie les 55 fichiers et affiche le compte attendu.

## 2. Contenu du livrable

| Fichier | Rôle |
|---|---|
| `build_corpus.sh` | Reconstruit le corpus de 55 fichiers |
| `ingest.py` | Pipeline d'ingestion (bibliothèque standard uniquement) |
| `verify.py` | Contrôles sur la sortie |
| `chunks.jsonl` | Les 468 chunks, un par ligne |
| `stats.json` | Bilan de l'exécution (fichiers, chunks, tailles) |
| `MANIFEST.txt` | Provenance : dépôt, commit, sélection |

## 3. Script d'ingestion

`ingest.py` :

1. charge les fichiers `.md`, `.markdown`, `.txt`, `.html`, `.htm` de façon récursive ;
2. extrait le texte brut : syntaxe Markdown et balises HTML retirées, titres conservés (pour HTML, `<script>`, `<style>`, `<nav>` et `<footer>` sont supprimés) ;
3. écarte les fichiers dont le contenu extrait est vide ;
4. découpe par titres (voir section 4) ;
5. attache à chaque chunk les métadonnées `source`, `doc_title`, `section` (chemin des titres), `chunk_index` (position dans le document), `split` (`header` ou `fixed`), `char_count` et `text` ;
6. écrit `chunks.jsonl` et `stats.json`.

Exécution, depuis le dossier du livrable, avec le corpus reconstruit :

```bash
python3 -I ingest.py --input corpus --output out --max-chars 1200 --overlap 150 --min-chars 200
python3 -I verify.py --corpus corpus --chunks out/chunks.jsonl
```

`-I` est utilisé parce que le script lit des fichiers non fiables.

## 4. Stratégie de découpage

- **Découpage par titres** : chaque section Markdown (titres `#` à `######`, hors blocs de code) devient un chunk. Le titre reste dans le texte pour que le chunk soit lisible seul.
- **Repli à taille fixe** : une section de plus de 1 200 caractères est coupée en fenêtres de 1 200 caractères avec 150 caractères de chevauchement. La coupure se fait sur un espace proche quand c'est possible.
- **Fusion des sections courtes** : une section de moins de 200 caractères (par exemple un titre sans contenu) est fusionnée avec la section suivante, ou avec la précédente si c'est la dernière. Sans cette règle, 34 chunks ne contenaient qu'un titre.

## 5. Résultats

| Indicateur | Valeur |
|---|---|
| Fichiers vus | 55 |
| Fichiers chargés | 54 |
| Fichiers écartés (contenu vide) | 1 (`reference/contributing.md`, qui ne contient qu'une directive d'inclusion) |
| **Nombre total de chunks** | **468** |
| Chunks issus du découpage par titres | 253 |
| Chunks issus du repli à taille fixe | 215 |
| **Taille moyenne d'un chunk** | **767,9 caractères** (≈ 190 tokens, estimation à 4 caractères par token) |
| Taille médiane | 753 caractères |
| Min / max | 94 / 1 199 caractères |

## 6. Vérifications

Ces résultats ont été reproduits : la reconstruction du corpus et l'ingestion donnent un `chunks.jsonl` identique octet pour octet à celui du livrable.

`verify.py` contrôle :

- les index `chunk_index` sont contigus de 0 à n−1 dans chaque document ;
- aucun chunk vide, et aucune ligne de bloc de code (```` ``` ````, `~~~`) ne reste dans le texte ;
- le découpage ne perd aucun mot : 11 670 mots sur 11 670 sont présents dans les chunks. Cette comparaison porte sur les sections produites par `ingest.py`. Le nettoyage du markup n'est pas testé ici, il l'est par la lecture des résultats.

Résultat actuel : `OK: all checks passed`.

Les formats `.html` et `.txt` ont été testés séparément sur deux petits fichiers de test, hors du corpus (le corpus ne contient que du Markdown). Pour le HTML, le menu, le script et les entités (`&amp;`) sont traités comme prévu. Pour le `.txt`, un document sans titre devient une section unique, étiquetée `header` même si elle n'a pas été découpée par titres.

## 7. Limites connues

- Les liens dont le texte s'étend sur plusieurs lignes (11 chunks concernés) ne sont pas nettoyés et gardent leur syntaxe `[texte](url)`. Le traitement se fait ligne par ligne.
- Une section fusionnée est étiquetée avec le titre de la section suivante, pas avec celui de la section d'origine.
- Les mots de code inline (`` `x` ``) perdent leurs backticks dans le texte brut, et les étiquettes de langage des blocs de code (`console`, `toml title=...`) sont retirées.
- La taille est mesurée en caractères, pas en tokens. L'équivalence en tokens est une estimation.
