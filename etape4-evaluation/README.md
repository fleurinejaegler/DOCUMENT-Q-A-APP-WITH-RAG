# Étape 4 — Journalisation et évaluation

## Fichiers

| Fichier | Rôle |
|---|---|
| `rag.py` | Recherche, prompt, génération, et journalisation JSONL (`make_record`, `log_interaction`) |
| `app.py` | Interface Streamlit : chaque question est journalisée |
| `eval_dataset.jsonl` | 20 questions : 18 répondables avec leurs fichiers sources attendus, 2 hors sujet |
| `evaluate.py` | Calcule le SourceHitRate@3 et prépare la feuille de revue manuelle |
| `test_step4.py` | Tests hors ligne (4) |
| `results/` | Sorties de la dernière évaluation |

## 1. Journalisation

Chaque question posée dans l'application ajoute une ligne à `logs/interactions.jsonl` (ou au chemin de `RAG_LOG_PATH`). Chaque ligne contient :

- `timestamp` (UTC, ISO 8601) et `question` ;
- `retrieved` : pour chacun des 3 chunks, `label`, `chunk_id`, `source`, `section`, `distance` et `score` (= 1 − distance, similarité cosinus) ;
- `answer`, `cited_labels`, `model`, et `error` si la génération a échoué.

## 2. Évaluation du SourceHitRate@3

```bash
python3 evaluate.py --db ../step2/chroma_db --dataset eval_dataset.jsonl --out results
```

Une question répondable est un **hit** si au moins un des 3 chunks récupérés provient d'un de ses fichiers sources attendus. Le SourceHitRate@3 est le nombre de hits divisé par le nombre de questions répondables. Les questions hors sujet sont exclues du taux.

**Résultat actuel** : 16 hits sur 18 questions répondables, soit **SourceHitRate@3 = 0,889**.

Échecs :
- `q01` « How do I create a new uv project? » : attendu `concepts/projects/init.md`, obtenu `index.md` et `features.md`.
- `q13` « What does uv run do in a project? » : attendu `concepts/projects/run.md`, obtenu `index.md`, `tools.md` et `build-backend.md`.

## 3. Revue manuelle des réponses

La revue demande des réponses générées, donc une clé API :

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python3 evaluate.py --db ../step2/chroma_db --dataset eval_dataset.jsonl --out results --generate
```

Le fichier `results/review.csv` contient une ligne par question, avec la colonne `answer` remplie. Remplis la colonne `label` avec une de ces valeurs :

- `Accurate` : réponse correcte et complète, citations cohérentes ;
- `Partially Accurate` : réponse correcte en partie, ou incomplète ;
- `Incorrect` : réponse fausse, ou qui s'appuie sur des passages qui ne la justifient pas ;
- `Not Answerable` : les documents ne couvrent pas la question, et la réponse devrait le dire. Les deux questions hors sujet attendent ce label.

Cette colonne n'est pas remplie dans le livrable, car elle demande un jugement humain sur de vraies réponses.

## 4. Tests

```bash
python3 test_step4.py
```

## Limites

- **Le jeu d'évaluation est petit** : 18 questions répondables. Un écart de 1 question change le taux de 5,6 points.
- **Les fichiers attendus ont été choisis d'après les titres des documents**, pas par lecture complète de chaque réponse. Une question peut donc avoir un fichier attendu qui ne contient pas la réponse exacte.
- **Les questions sont en anglais**, car le corpus est en anglais. Le modèle d'embedding `all-MiniLM-L6-v2` est anglophone.
- **Les réponses n'ont pas été générées** pour cette livraison, faute de clé API dans l'environnement. La revue manuelle reste à faire.
