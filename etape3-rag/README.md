# Étape 3 — Pipeline RAG et interface Streamlit

## Fichiers

| Fichier | Rôle |
|---|---|
| `rag.py` | Recherche sémantique (top 3), construction du prompt RAG, appel au LLM |
| `app.py` | Interface Streamlit : question, réponse, sources, contexte récupéré |
| `test_step3.py` | Tests hors ligne (le LLM est simulé) |
| `requirements.txt` | Versions testées |

Ce dossier utilise l'index créé à l'étape 2 : `../step2/chroma_db`, collection `docs`.

## Installation et lancement

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=ta_clé        # sans cette variable, seul le contexte récupéré s'affiche
streamlit run app.py
```

Le modèle de génération est `claude-haiku-5-5`. Pour en changer : `export LLM_MODEL=...`.

## Fonctionnement

1. **Recherche** : la question est encodée avec `all-MiniLM-L6-v2`, puis les 3 chunks les plus proches sont récupérés dans ChromaDB (similarité cosinus).
2. **Prompt** : les passages sont numérotés `[1]`, `[2]`, `[3]` avec leur source et leur section. Le message système demande de répondre uniquement à partir de ces passages, de citer avec les étiquettes entre crochets, et de dire quand la réponse n'est pas dans les documents.
3. **Génération** : appel à l'API Anthropic. Sans clé, la fonction lève une erreur claire et l'interface affiche les passages récupérés.
4. **Affichage** : réponse, liste des sources avec une coche pour celles effectivement citées, et une section repliable par passage.

## Tests

```bash
python3 test_step3.py
```

Résultat : 7 tests passent. Ils couvrent la recherche (3 passages, étiquettes 1 à 3), le prompt, l'extraction des citations, le chemin sans clé, et deux parcours de l'interface Streamlit (sans clé, puis avec une réponse simulée).

## Limites

- **Le LLM réel n'a pas été appelé pendant la vérification**, faute de clé dans l'environnement. Les tests utilisent une réponse simulée. La première vraie génération doit être vérifiée sur ta machine.
- La qualité de la recherche dépend de l'étape 2 : sur le jeu de test de l'étape 2, hit@3 était de 4/6. Si une réponse est fausse, c'est souvent la récupération qui manque, pas le LLM.
- Les chunks dépassant 256 tokens sont tronqués à l'encodage (voir l'étape 2).
