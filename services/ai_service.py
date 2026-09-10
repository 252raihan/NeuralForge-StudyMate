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
