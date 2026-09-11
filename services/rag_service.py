"""RAG (Retrieval-Augmented Generation) service for NeuralForge StudyMate (Step 11).

Provides lightweight, local document chunking, keyword-based retrieval over
APPROVED material chunks, and context building for the StudyMate Q&A flow.

Design notes:
- No external vector database is required yet. Retrieval uses SQLite + Python
  text scoring. The public functions (`chunk_text`, `retrieve_relevant_chunks`,
  `build_rag_context`) are intentionally stable so a future embeddings/vector
  backend can replace the scoring internals WITHOUT changing the Q&A API.
- All content is treated as UNTRUSTED DATA. Nothing here executes document text.
"""

import os
import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Configurable constants (tunable via environment without code changes)
# ---------------------------------------------------------------------------
CHUNK_SIZE = int(os.environ.get("RAG_CHUNK_SIZE", "1500"))          # ~1200-1800 chars
CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "200"))    # ~150-250 chars
MAX_CHUNK_SIZE = int(os.environ.get("RAG_MAX_CHUNK_SIZE", "3000")) # hard ceiling
MAX_TOP_K = int(os.environ.get("RAG_MAX_TOP_K", "8"))              # never exceed
MAX_CANDIDATE_CHUNKS = int(os.environ.get("RAG_MAX_CANDIDATE_CHUNKS", "400"))
MAX_CONTEXT_CHARS = int(os.environ.get("RAG_MAX_CONTEXT_CHARS", "12000"))
MIN_RELEVANCE_SCORE = float(os.environ.get("RAG_MIN_RELEVANCE_SCORE", "1.0"))
DEPARTMENT_BOOST = float(os.environ.get("RAG_DEPARTMENT_BOOST", "0.75"))

# Short list of common English stop words — cheap and sufficient for study Q&A.
STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "of", "to", "in",
    "on", "at", "by", "for", "with", "about", "into", "from", "as", "is", "are",
    "was", "were", "be", "been", "being", "am", "do", "does", "did", "doing",
    "have", "has", "had", "having", "what", "which", "who", "whom", "this",
    "that", "these", "those", "it", "its", "how", "why", "when", "where", "can",
    "could", "should", "would", "will", "shall", "may", "might", "must", "explain",
    "define", "describe", "tell", "give", "list", "discuss", "please", "help",
    "need", "want", "know", "understand", "difference", "between", "using", "use",
})

NO_MATCH_ANSWER = (
    "I couldn't find enough relevant information in the approved study materials "
    "to answer this confidently."
)


# ---------------------------------------------------------------------------
# Query preprocessing
# ---------------------------------------------------------------------------
def preprocess_question(question: str) -> Dict[str, Any]:
    """Normalize a raw question into lowercased terms, keeping a full phrase.

    Returns a dict with:
      - terms: list of significant single-word tokens
      - phrase: the normalized full query (for exact-phrase matching)
    """
    normalized = (question or "").casefold()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    tokens = re.findall(r"[a-z0-9]+", normalized)
    terms = [t for t in tokens if len(t) > 2 and t not in STOP_WORDS]
    return {"terms": terms[:24], "phrase": normalized}


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split extracted text into overlapping, non-empty chunks.

    Strategy: character-based windowing that tries to break on a paragraph or
    sentence boundary near the target size, while guaranteeing:
      - no empty/whitespace-only chunks
      - a hard maximum chunk size (MAX_CHUNK_SIZE)
      - the configured overlap between consecutive chunks
    """
    if not text or not isinstance(text, str):
        return []

    clean = re.sub(r"[ \t]+", " ", text)
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    if not clean:
        return []

    chunk_size = max(200, min(int(chunk_size or CHUNK_SIZE), MAX_CHUNK_SIZE))
    overlap = max(0, min(int(overlap or 0), chunk_size // 2))

    chunks: List[str] = []
    start = 0
    length = len(clean)
    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            window = clean[start:end]
            boundary = max(
                window.rfind("\n\n"), window.rfind(". "),
                window.rfind("? "), window.rfind("! "),
            )
            if boundary == -1:
                boundary = window.rfind(" ")
            if boundary > chunk_size // 2:
                end = start + boundary + 1
        piece = clean[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return chunks



# ---------------------------------------------------------------------------
# Scoring (isolated so it can be swapped for embeddings later)
# ---------------------------------------------------------------------------
def _score_chunk(chunk: Dict[str, Any], query: Dict[str, Any],
                 student_department_id: Optional[int]) -> float:
    """Compute a relevance score for one chunk against a preprocessed query.

    Signals (approximate):
      - exact phrase match  -> strongest
      - multiple distinct query terms present -> compounding
      - topic / course name / course code match -> partial boost
      - small department preference boost (never overrides relevance)
    """
    content = (chunk.get("content") or "").casefold()
    topic = (chunk.get("topic") or "").casefold()
    course_name = (chunk.get("course_name") or "").casefold()
    course_code = (chunk.get("course_code") or "").casefold()

    terms = query.get("terms") or []
    phrase = query.get("phrase") or ""
    score = 0.0

    # Exact phrase match is the strongest single signal.
    if phrase and len(phrase) > 3 and phrase in content:
        score += 5.0
    if phrase and phrase in topic:
        score += 3.0

    matched_terms = 0
    for term in terms:
        in_content = content.count(term)
        if in_content:
            matched_terms += 1
            score += min(in_content, 4) * 1.0
        if term in topic:
            score += 2.0
        if term in course_name:
            score += 1.0
        if term in course_code:
            score += 1.5

    # Reward chunks that contain several distinct query terms.
    if matched_terms > 1:
        score += (matched_terms - 1) * 1.5

    # Small department preference: additive, never dominant over relevance.
    if student_department_id and chunk.get("department_id") == student_department_id and score > 0:
        score += DEPARTMENT_BOOST

    return score


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
def retrieve_relevant_chunks(question: str, student_department_id: Optional[int] = None,
                             top_k: int = 5, conn=None) -> List[Dict[str, Any]]:
    """Retrieve the top-K relevant chunks from APPROVED materials only.

    Approval is enforced server-side in SQL (status = 'approved'); pending and
    rejected materials can never be returned, regardless of caller input.
    The scan is bounded by MAX_CANDIDATE_CHUNKS to protect performance.
    """
    from database.db import get_db_connection  # lazy import avoids a cycle
    query = preprocess_question(question)
    if not query["terms"] and not query["phrase"]:
        return []

    top_k = max(1, min(int(top_k or 5), MAX_TOP_K))
    own = conn is None
    conn = conn or get_db_connection()
    try:
        # Parameterized, approved-only, bounded query. No dynamic SQL.
        rows = conn.execute(
            "SELECT mc.id AS chunk_id, mc.material_id, mc.chunk_index, mc.content, "
            "sm.topic, sm.exam_type, c.course_name, c.course_code, c.department_id "
            "FROM material_chunks mc "
            "JOIN study_materials sm ON mc.material_id = sm.id "
            "JOIN courses c ON sm.course_id = c.id "
            "WHERE sm.status = 'approved' "
            "ORDER BY mc.material_id DESC, mc.chunk_index ASC LIMIT ?",
            (MAX_CANDIDATE_CHUNKS,),
        ).fetchall()

        scored: List[Dict[str, Any]] = []
        for row in rows:
            chunk = dict(row)
            score = _score_chunk(chunk, query, student_department_id)
            if score >= MIN_RELEVANCE_SCORE:
                chunk["score"] = round(score, 3)
                scored.append(chunk)

        scored.sort(key=lambda c: (-c["score"], -c["material_id"], c["chunk_index"]))
        return scored[:top_k]
    finally:
        if own:
            conn.close()


def group_chunks_by_material(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate source attribution while keeping the best chunks per material.

    Returns one entry per material (most relevant first) carrying the retained
    chunks, so the UI shows a single source card per document.
    """
    grouped: Dict[int, Dict[str, Any]] = {}
    for chunk in chunks:
        mid = chunk["material_id"]
        entry = grouped.get(mid)
        if entry is None:
            grouped[mid] = {
                "material_id": mid,
                "course_name": chunk.get("course_name"),
                "course_code": chunk.get("course_code"),
                "topic": chunk.get("topic"),
                "exam_type": chunk.get("exam_type"),
                "score": chunk.get("score", 0.0),
                "chunks": [chunk],
            }
        else:
            entry["chunks"].append(chunk)
            if chunk.get("score", 0.0) > entry["score"]:
                entry["score"] = chunk.get("score", 0.0)
    return sorted(grouped.values(), key=lambda entry: -entry["score"])


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------
def build_rag_context(retrieved_chunks: List[Dict[str, Any]],
                      max_context_chars: int = MAX_CONTEXT_CHARS) -> Dict[str, Any]:
    """Build a bounded, prioritized AI context string from retrieved chunks.

    - Highest-scoring chunks are included first.
    - A hard character limit is respected (nothing overflows to the model).
    - Only safe metadata (course, code, topic) is included — never file paths
      or hidden database columns.

    Returns the context string, the chunk count, and whether truncation occurred.
    """
    limit = max(500, min(int(max_context_chars or MAX_CONTEXT_CHARS), MAX_CONTEXT_CHARS))
    ordered = sorted(retrieved_chunks, key=lambda c: -c.get("score", 0.0))

    parts: List[str] = []
    used = 0
    included = 0
    truncated = False
    for idx, chunk in enumerate(ordered, start=1):
        header = (
            "[Source " + str(idx) + "]\n"
            "Course: " + str(chunk.get("course_name") or "Unknown") + "\n"
            "Code: " + str(chunk.get("course_code") or "N/A") + "\n"
            "Topic: " + str(chunk.get("topic") or "N/A") + "\n\n"
            "Relevant content:\n"
        )
        content = (chunk.get("content") or "").strip()
        block = header + content
        if used + len(block) > limit:
            remaining = limit - used - len(header)
            if remaining > 100:
                parts.append(header + content[:remaining])
                used += len(header) + remaining
                included += 1
            truncated = True
            break
        parts.append(block)
        used += len(block)
        included += 1
    return {
        "context": "\n\n".join(parts),
        "chunk_count": included,
        "truncated": truncated,
        "chars_used": used,
    }


# ---------------------------------------------------------------------------
# End-to-end RAG helper (stable interface for the Q&A route)
# ---------------------------------------------------------------------------
def retrieve_context(question: str, student_department_id: Optional[int] = None,
                     top_k: int = 5, max_context_chars: int = MAX_CONTEXT_CHARS) -> Dict[str, Any]:
    """Question -> preprocess -> retrieve -> group -> build context.

    Returns a dict with the context string, grouped sources, and counts. This
    keeps the retrieval algorithm out of the Flask route while presenting a
    stable interface for a future embeddings backend.
    """
    chunks = retrieve_relevant_chunks(question, student_department_id, top_k=top_k)
    built = build_rag_context(chunks, max_context_chars=max_context_chars)
    return {
        "chunks": chunks,
        "sources": group_chunks_by_material(chunks),
        "context": built["context"],
        "chunk_count": built["chunk_count"],
        "truncated": built["truncated"],
        "has_relevant": len(chunks) > 0,
    }



# ---------------------------------------------------------------------------
# Indexing / re-indexing (Step 11 section 12)
# ---------------------------------------------------------------------------
def index_material(material_id: int, conn=None) -> int:
    """(Re)build the chunk index for one material from its stored text.

    - Loads the material's extracted text (any status; approval is enforced at
      RETRIEVAL time, not indexing time).
    - Removes existing chunks and regenerates fresh ones (idempotent).
    - Returns the number of chunks stored.
    """
    from database.db import get_material_extracted_text, save_material_chunks
    try:
        text = get_material_extracted_text(material_id, conn=conn)
    except TypeError:
        text = get_material_extracted_text(material_id)
    if not text or not text.strip():
        # No usable text -> ensure no stale chunks remain.
        from database.db import delete_material_chunks
        delete_material_chunks(material_id, conn=conn)
        return 0
    chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
    return save_material_chunks(material_id, chunks, conn=conn)
