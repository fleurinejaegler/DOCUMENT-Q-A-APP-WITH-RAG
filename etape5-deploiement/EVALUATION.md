# Évaluation du système RAG

## 1. Corpus et index

- **Corpus** : documentation du projet open-source [astral-sh/uv](https://github.com/astral-sh/uv), dossier `docs/` au commit `d5c3f17`, sans `docs/guides/`. 55 fichiers Markdown, 54 chargés (1 fichier ne contient qu'une directive d'inclusion).
- **Découpage** : par titres, avec repli à taille fixe de 1 200 caractères et chevauchement de 150. Sections de moins de 200 caractères fusionnées. Résultat : 468 chunks, 768 caractères en moyenne.
- **Index** : ChromaDB, embeddings `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, similarité cosinus).

## 2. Jeu d'évaluation

Fichier : `etape4-evaluation/eval_dataset.jsonl`. 20 questions en anglais :

- **18 questions répondables**, chacune associée à un ou plusieurs fichiers sources attendus. Les fichiers ont été choisis d'après les titres des documents.
- **2 questions hors sujet** (« What is the capital of Australia? », « What will the price of uv Pro be next year? »). Elles n'ont pas de source attendue et servent à tester le label « Not Answerable ».

Limite : le jeu est petit, et un seul échec change le taux de 5,6 points.

## 3. SourceHitRate@3

Une question répondable est un **hit** si au moins un des 3 chunks récupérés provient d'un de ses fichiers attendus.

| Mesure | Valeur |
|---|---|
| Questions répondables | 18 |
| Hits | 16 |
| **SourceHitRate@3** | **0,889** |

Échecs :

| Question | Source attendue | Top 3 obtenu |
|---|---|---|
| « How do I create a new uv project? » | `concepts/projects/init.md` | `index.md`, `features.md`, `index.md` |
| « What does uv run do in a project? » | `concepts/projects/run.md` | `index.md`, `tools.md`, `build-backend.md` |

Constats :

- **Des doublons dans le top 3** : pour plusieurs questions, les 3 chunks viennent du même document. Par exemple, « TLS certificates » remonte 3 fois `certificates.md`. Un seul document peut alors occuper tout le contexte.
- **`index.md` attire les requêtes générales** : c'est une page d'accueil, et elle remonte pour « create », « install » ou « run ».

## 4. Qualité des réponses

**Non mesurée à ce stade.** La revue manuelle demande de vraies réponses générées par le LLM, et les réponses n'ont pas été produites dans l'environnement de travail (pas de clé API). La colonne `label` de `results/review.csv` reste à remplir avec l'une de ces valeurs :

- Accurate
- Partially Accurate
- Incorrect
- Not Answerable

Une fois la revue faite, ce tableau doit être rempli :

| Label | Nombre de réponses |
|---|---|
| Accurate | à remplir |
| Partially Accurate | à remplir |
| Incorrect | à remplir |
| Not Answerable | à remplir |

## 5. Pistes d'amélioration

Ces pistes viennent directement des constats ci-dessus :

1. **Troncature des chunks** : 134 chunks sur 468 dépassent les 256 tokens du modèle, et leur fin est ignorée à l'encodage. Un découpage à 800 caractères réduit ce nombre à 23 (test réalisé, sans changement sur ce jeu de questions).
2. **Diversité du contexte** : limiter à un chunk par document, ou utiliser une sélection de type MMR, pour que le top 3 couvre plusieurs sources.
3. **Recherche hybride** : combiner la recherche sémantique avec une recherche par mots-clés (BM25). Les requêtes courtes comme « run » ou « create » en profiteraient.
4. **Reranking** : un modèle de reranking sur les 10 premiers résultats, pour remonter les bons chunks dans le top 3.
5. **Jeu d'évaluation plus grand** : 50 questions ou plus, avec plusieurs formulations par question, pour des mesures moins fragiles.
6. **Questions en français** : le modèle `all-MiniLM-L6-v2` est anglophone. Le corpus étant en anglais, il faudrait un modèle multilingue pour accepter des questions en français.
