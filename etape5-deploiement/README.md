# Questions sur la documentation uv — application RAG

**Démo en ligne** : *à compléter après le déploiement* (lien Streamlit Community Cloud ou Hugging Face Spaces).

Application qui répond à des questions sur la documentation de [uv](https://github.com/astral-sh/uv) à partir des passages retrouvés dans la documentation, avec des citations vers les sources.

## Architecture

```
docs Markdown (uv, 55 fichiers)
   │  ingestion : extraction du texte, découpage par titres
   │  repli à taille fixe (1 200 caractères, chevauchement 150)
   ▼
468 chunks  ──►  embeddings all-MiniLM-L6-v2  ──►  ChromaDB (chroma_db/)
                                                       │
question ──► embedding ──► top 3 chunks ◄──────────────┘
                              │
                              ▼
        prompt RAG : réponse à partir des passages seulement,
        citations [1] [2] [3]
                              │
                              ▼
                 LLM claude-haiku-5-5 (API Anthropic)
                              │
                              ▼
   interface Streamlit : réponse, sources, passages, journal JSONL
```

Fichiers principaux :

| Fichier | Rôle |
|---|---|
| `deploy/app.py` | Interface Streamlit |
| `deploy/rag.py` | Recherche, prompt, appel au LLM, journalisation |
| `deploy/chroma_db/` | Index ChromaDB (468 chunks) |
| `deploy/requirements.txt` | Dépendances |
| `deploy/test_deploy.py` | Tests de l'application déployable |
| `EVALUATION.md` | Jeu d'évaluation, SourceHitRate@3, revue des réponses |

## Installation locale

Python 3.10 ou plus est nécessaire.

```bash
cd deploy
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."     # sans cette variable, seuls les passages récupérés s'affichent
streamlit run app.py
```

Ouvre ensuite `http://localhost:8501`.

Pour reconstruire l'index à partir des chunks, voir les étapes 1 et 2 du dépôt (`etape1-ingestion/`, `etape2-indexation/`).

## Déploiement

**Streamlit Community Cloud**

1. Pousse ce dépôt sur GitHub.
2. Sur share.streamlit.io, crée une application à partir du dépôt, avec le fichier principal `deploy/app.py`.
3. Dans les paramètres de l'application, section *Secrets*, ajoute :

   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```

**Limite à vérifier** : `torch` et `sentence-transformers` sont lourds. Sur un hébergement à mémoire limitée, l'application peut ne pas démarrer. Hugging Face Spaces (SDK Streamlit) est une alternative.

## Exemples de questions

- How do I pin the Python version for a project?
- What does uv sync do?
- How do I export a lockfile to requirements.txt format?
- Where does uv store its cache?
- How do I use custom CA certificates for TLS?
- What is a uv workspace?
- What is uv tool run used for?
- How do I enable preview features in uv?

Les questions doivent être en anglais, car le corpus et le modèle d'embedding sont anglophones.

## Limites connues

- **Corpus restreint** : seuls 55 fichiers de la documentation uv sont indexés. Le dossier `docs/guides/` est exclu.
- **Recherche imparfaite** : sur le jeu d'évaluation, le SourceHitRate@3 est de 0,889 (16 hits sur 18 questions répondables). Des questions générales comme « how do I create a new project » peuvent ne pas remonter la bonne page. Voir `EVALUATION.md`.
- **Doublons dans le contexte** : les 3 passages peuvent venir du même document.
- **Troncature à l'encodage** : 134 chunks dépassent 256 tokens. Leur fin n'entre pas dans l'embedding.
- **Questions en anglais uniquement** : le modèle d'embedding est anglophone.
- **Qualité des réponses non mesurée** : la revue manuelle reste à faire (voir `EVALUATION.md`).
- **Journal non persistant** sur certains hébergements : le système de fichiers peut être éphémère, et le journal `logs/interactions.jsonl` peut disparaître au redémarrage.
- **Dépendance à une clé API** : sans `ANTHROPIC_API_KEY`, l'application affiche seulement les passages récupérés.
