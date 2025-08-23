# Guide des fonctions – `agent_openAI.py`

### `normalize(text: str) -> str`
Nettoie une chaîne : normalisation, suppression des caractères spéciaux inutiles.

### `chunk_text(text: str, max_length: int = 300) -> List[str]`
Découpe un long texte en morceaux (~phrases) d’au plus `max_length` caractères. Sert à créer des « chunks » RAG consommables par l’index vectoriel.

### `_normalize_smart_quotes(s: str) -> str`
Remplace les guillemets typographiques par des guillemets simples/doubles ASCII. Évite des erreurs SQL.

### `clean_sql(sql: str) -> str`
Nettoie une requête SQL : enlève les fences Markdown ```sql … ```, normalise les guillemets, supprime un `;` final superflu.

### `extract_sql(text: str) -> Optional[str]`
Repère et extrait la **première** requête SQL (SELECT/INSERT/UPDATE/DELETE) présente dans un texte, jusqu’au premier `;` ou la fin. Retourne `None` si rien trouvé.

### `sanitize_sql_literals(sql: str) -> str`
Sécurise légèrement les **littéraux texte** dans la requête :
- enlève **tout backtick** qui se glisserait *à l’intérieur* d’une chaîne `'...'` ;
- si une quote de fin manque, la **ferme** pour éviter un SQL cassé.
Ne dépend pas du schéma métier.

---

## Indexation & RAG

### `_make_embeddings()`
Construit l’embedder OpenAI (`text-embedding-3-small`) pour Chroma.

### `_context_last_mtime() -> float`
Renvoie le timestamp « modification la plus récente » parmi les fichiers de contexte (schema/patterns/etc.).

### `_index_last_mtime() -> float`
Renvoie le mtime du dossier d’index vectoriel (ou `0.0` s’il n’existe pas).

### `load_documents() -> List[Document]`
Charge les fichiers de contexte JSON (`schema_description.json`, `rag_table_relationships.json`, `table_domains.json`, `query_patterns.json`) et fabrique une liste de `Document` (texte + métadonnées) pour l’index. Découpe les grandes descriptions en morceaux via `chunk_text`.

### `build_rag_index()`
(Re)construit l’index Chroma **en réinitialisant la collection** puis en ajoutant les documents retournés par `load_documents()`. Persiste l’index sur disque.

### `auto_rebuild_if_needed()`
Compare les dates de modification du contexte et de l’index. Si le contexte est plus récent, reconstruit l’index.

---

## Exécution SQL & NLG

### `execute_sql(sql: str) -> Tuple[Optional[List[dict]], Optional[str]]`
Exécute la requête via `mysql.connector` avec un curseur `dictionary=True`.
- `SELECT` → retourne la **liste de lignes** (chaque ligne est un dict).
- `INSERT/UPDATE/DELETE` → commit et retourne `[{ "rows_affected": N }]`.
En cas d’exception, retourne `(None, "message d’erreur")`.

### `to_natural_language(question: str, rows: Optional[List[dict]], error: Optional[str]) -> str`
Transforme le résultat SQL en **réponse française** claire et compacte (générique, pas de cas métier codés en dur).
- Si `error` est présent → renvoie un message d’erreur lisible.
- Sinon : calcule `row_count`, prend un échantillon (≤ 30 lignes) et demande au LLM de **résumer** sans afficher du SQL/JSON.
- Fallback déterministe si le LLM échoue : liste clé : valeur sur 10 lignes max, ou « Aucune donnée trouvée ».

---

## Classe `SQLAssistant`

### `__init__(self)`
Initialise :
- l’embedder et la base Chroma (lecture) ;
- le client LLM (`gpt-4o`) ;
- l’accès SQLAlchemy à MySQL pour `get_table_info()` éventuel ;
- le cache (fichier JSON).

### `_load_cache(self) -> dict` / `_save_cache(self)`
Lit/écrit le cache sur disque (`question_cache.json`). Le cache stocke pour chaque question la SQL générée et la réponse naturelle.

### `_save_history(self, question, sql, response)`
Append un enregistrement (timestamp, question, SQL, réponse) dans `query_history.json` pour audit/débogage.

### `retrieve_context(self, question: str, k=6) -> List[str]`
Recherche vectorielle dans Chroma avec la question. Ne garde que les résultats avec un score suffisamment bon et renvoie la **liste des contenus** (strings) à injecter dans le prompt SQL.

### `ask_llm(self, prompt: str) -> str`
Envoie un prompt au modèle de chat et renvoie le **texte** retourné (trim).

### `ask(self, question: str) -> str`
Orchestre le pipeline complet :
1. Cherche la réponse dans le **cache**.
2. Récupère le **contexte** (RAG) et l’affiche si l’option est active.
3. Construit un **prompt SQL** (règles de jointures, année scolaire, quoting).
4. Génère la SQL via `ask_llm`, l’extrait avec `extract_sql`, la nettoie avec `clean_sql`, puis **sanitise** les littéraux avec `sanitize_sql_literals`.
5. Exécute la SQL (`execute_sql`) et convertit le résultat en texte (`to_natural_language`).
6. Met à jour le **cache** et l’**historique**.  
Renvoie la **réponse en français**.

---

## `main()`
Démarre l’assistant en mode CLI : reconstruit l’index si nécessaire, instancie `SQLAssistant`, puis boucle sur les questions de l’utilisateur (sortie avec `exit`/`quit`).

