"""
AI Service for NeuralForge StudyMate (Step 4).
Generates structured study summaries from extracted PDF text using the OpenAI API.
"""

import os
from openai import OpenAI, APIError, AuthenticationError, RateLimitError, APIConnectionError

# Maximum character limit sent to OpenAI in Step 4.
# ~15,000 characters is roughly 3,000-3,750 tokens, keeping latency and costs low
# while easily accommodating standard study notes, lecture slides, and article excerpts.
MAX_INPUT_CHAR_LIMIT = 15000

# Default model
DEFAULT_MODEL = "gpt-4o-mini"


def get_openai_client() -> OpenAI:
    """
    Retrieves an initialized OpenAI client using the OPENAI_API_KEY
    environment variable.
    Raises ValueError if the key is missing or set to a placeholder.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not api_key or api_key == "your-api-key-here":
        raise ValueError(
            "OpenAI API key is missing or not configured. "
            "Please add your valid OPENAI_API_KEY to the .env file."
        )

    return OpenAI(api_key=api_key)


def generate_pdf_summary(extracted_text: str) -> dict:
    """
    Generates a structured study summary from extracted PDF text.

    The summary includes:
    1. Short overview
    2. Key points
    3. Important concepts
    4. Important definitions (when applicable)

    :param extracted_text: The raw text extracted from the PDF.
    :return: Dictionary containing:
             {
                 "success": True,
                 "summary": str,
                 "model_used": str,
                 "truncated": bool,
                 "original_length": int,
                 "processed_length": int
             }
    """
    if not extracted_text or not extracted_text.strip():
        raise ValueError("Cannot summarize empty text. Please provide valid PDF text.")

    clean_text = extracted_text.strip()
    original_length = len(clean_text)
    is_truncated = False

    # Apply safe input length limit
    if original_length > MAX_INPUT_CHAR_LIMIT:
        clean_text = clean_text[:MAX_INPUT_CHAR_LIMIT]
        is_truncated = True

    model_name = os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    client = get_openai_client()

    system_prompt = (
        "You are an expert academic tutor and study assistant. "
        "Your goal is to turn raw study materials into clear, high-yield study summaries.\n\n"
        "Format your summary with clean Markdown using the following exact sections:\n"
        "### 1. Overview\n"
        "A concise 2-3 sentence executive summary of what this document covers.\n\n"
        "### 2. Key Points\n"
        "Bulleted highlights of the most important ideas, takeaways, or arguments.\n\n"
        "### 3. Core Concepts\n"
        "Explanations of central principles, methodologies, or frameworks introduced.\n\n"
        "### 4. Important Definitions\n"
        "List key terms and their clear, beginner-friendly definitions (if no specific terms exist, note that)."
    )

    user_prompt = (
        "Please generate a comprehensive, structured study summary of the following document text:\n\n"
        "--- DOCUMENT TEXT BEGIN ---\n"
        f"{clean_text}\n"
        "--- DOCUMENT TEXT END ---"
    )

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )

        summary_content = response.choices[0].message.content

        return {
            "success": True,
            "summary": summary_content,
            "model_used": model_name,
            "truncated": is_truncated,
            "original_length": original_length,
            "processed_length": len(clean_text),
        }

    except AuthenticationError:
        raise ValueError(
            "Authentication failed: Invalid OpenAI API key. "
            "Please check the OPENAI_API_KEY in your .env file."
        )
    except RateLimitError:
        raise ValueError(
            "OpenAI API rate limit exceeded or insufficient quota. "
            "Please check your OpenAI account billing and quota limits."
        )
    except APIConnectionError:
        raise ValueError(
            "Could not connect to OpenAI API. Please check your internet connection."
        )
    except APIError as api_err:
        raise ValueError(f"OpenAI API error: {api_err.message}")
    except Exception as exc:
        raise ValueError(f"Unexpected error while generating summary: {str(exc)}")


# Step 10 quiz generation ----------------------------------------------------
QUIZ_TYPES = {"mcq", "short", "mixed"}
DIFFICULTIES = {"easy", "medium", "hard", "mixed"}


def _validate_quiz_questions(payload, requested_type, requested_difficulty, count):
    # Validate and normalize model output before it can be persisted.
    import json
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError) as exc:
            raise ValueError("The AI returned invalid quiz data.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("questions"), list):
        raise ValueError("The AI returned an invalid quiz structure.")
    questions = payload["questions"]
    if len(questions) != count:
        raise ValueError("The AI did not generate the requested number of questions.")
    normalized = []
    seen = set()
    expected_types = {requested_type} if requested_type != "mixed" else {"mcq", "short"}
    allowed_difficulties = {requested_difficulty} if requested_difficulty != "mixed" else {"easy", "medium", "hard"}
    for item in questions:
        if not isinstance(item, dict):
            raise ValueError("The AI returned an invalid question.")
        kind = item.get("type")
        text = item.get("question")
        difficulty = item.get("difficulty")
        explanation = item.get("explanation")
        if not all(isinstance(value, str) for value in (kind, text, difficulty, explanation)):
            raise ValueError("The AI returned invalid quiz fields.")
        kind = kind.strip().lower()
        text = text.strip()
        difficulty = difficulty.strip().lower()
        explanation = explanation.strip()
        key = text.casefold()
        if kind not in expected_types or not text or not explanation or not difficulty in allowed_difficulties or key in seen:
            raise ValueError("The AI returned invalid or duplicate quiz questions.")
        seen.add(key)
        row = {"question_type": kind, "question": text, "explanation": explanation, "difficulty": difficulty}
        if kind == "mcq":
            options = item.get("options")
            correct = item.get("correct_answer")
            if not isinstance(options, list) or len(options) != 4 or any(not isinstance(x, str) or not x.strip() for x in options) or not isinstance(correct, str) or not correct.strip():
                raise ValueError("The AI returned an invalid multiple-choice question.")
            options = [str(x).strip() for x in options]
            if len({x.casefold() for x in options}) != 4 or correct not in options:
                raise ValueError("The AI returned an invalid answer key.")
            row.update({"options_json": json.dumps(options), "correct_answer": correct, "expected_answer": None})
        else:
            expected = item.get("expected_answer")
            if not isinstance(expected, str) or not expected.strip():
                expected = ""
            else:
                expected = expected.strip()
            if not expected:
                raise ValueError("The AI returned an invalid short question.")
            row.update({"options_json": None, "correct_answer": None, "expected_answer": expected})
        normalized.append(row)
    if requested_type == "mixed":
        mcq_count = sum(q["question_type"] == "mcq" for q in normalized)
        if mcq_count != (count + 1) // 2:
            raise ValueError("The AI did not follow the required mixed-question distribution.")
    return normalized

def generate_quiz_questions(extracted_text, question_type, difficulty, count):
    # Generate a validated quiz using the existing server-side OpenAI client.
    import json
    if not extracted_text or not extracted_text.strip():
        raise ValueError("Study material content is empty.")
    if question_type not in QUIZ_TYPES or difficulty not in DIFFICULTIES:
        raise ValueError("Invalid quiz options.")
    if not isinstance(count, int) or not 1 <= count <= 20:
        raise ValueError("Question count must be between 1 and 20.")
    clean_text = extracted_text.strip()[:MAX_INPUT_CHAR_LIMIT]
    mixed_mcq_count = (count + 1) // 2
    distribution = ("exactly " + str(mixed_mcq_count) + " MCQ and " + str(count - mixed_mcq_count) + " short questions") if question_type == "mixed" else "all " + question_type.upper() + " questions"
    prompt = ("Use only the supplied study material. Do not invent facts or use unrelated knowledge. "
              f"Generate exactly {count} questions as {distribution}. Respect requested difficulty '{difficulty}'. "
              "Avoid duplicates. MCQs must have exactly four options and one correct option. "
              "Every question needs an explanation. Return only valid JSON with a questions array.\n\n"
              f"Study material:\n---\n{clean_text}\n---")
    client = get_openai_client()
    model_name = os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a careful academic quiz generator. Return JSON only."},
                {"role": "user", "content": prompt},
            ], temperature=0.2,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return _validate_quiz_questions(content, question_type, difficulty, count)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Quiz generation is temporarily unavailable.") from exc
