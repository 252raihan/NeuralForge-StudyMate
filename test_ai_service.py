"""
Test suite for Step 4: AI Service and /summarize endpoint.
Verifies input validation, safe length truncation, error handling,
and structured response formatting.
"""

import os
import unittest
from unittest.mock import MagicMock, patch
from services.ai_service import generate_pdf_summary, MAX_INPUT_CHAR_LIMIT
from app import app


class TestAiService(unittest.TestCase):
    def setUp(self):
        # Consistent with the other suites: CSRF is disabled only for the test
        # client; production CSRF protection is covered by test_security_step15.
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_missing_or_placeholder_key_raises_value_error(self):
        """Verifies that placeholder or missing API key is cleanly caught."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "your-api-key-here"}):
            with self.assertRaises(ValueError) as ctx:
                generate_pdf_summary("Some sample document text")
            self.assertIn("API key is missing or not configured", str(ctx.exception))

    def test_empty_text_raises_value_error(self):
        """Verifies that empty input text is rejected."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-valid-format"}):
            with self.assertRaises(ValueError) as ctx:
                generate_pdf_summary("   ")
            self.assertIn("Cannot summarize empty text", str(ctx.exception))

    @patch("services.ai_service.OpenAI")
    def test_safe_length_truncation_for_large_input(self, mock_openai_cls):
        """Verifies that inputs exceeding MAX_INPUT_CHAR_LIMIT are safely truncated."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = "### 1. Overview\nMock summary\n### 2. Key Points\n- Point 1\n### 3. Core Concepts\n- Concept 1\n### 4. Important Definitions\nNone."
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        huge_text = ("NeuralForge study note. " * 1500).strip()  # ~36,000 characters
        self.assertGreater(len(huge_text), MAX_INPUT_CHAR_LIMIT)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-valid-key-for-test"}):
            result = generate_pdf_summary(huge_text)
            self.assertTrue(result["truncated"])
            self.assertEqual(result["processed_length"], MAX_INPUT_CHAR_LIMIT)
            self.assertEqual(result["original_length"], len(huge_text))
            self.assertIn("Mock summary", result["summary"])

    @patch("app.generate_pdf_summary")
    def test_summarize_endpoint_success(self, mock_generate):
        """Verifies /summarize endpoint returns structured JSON on success."""
        mock_generate.return_value = {
            "success": True,
            "summary": "### 1. Overview\nDocument overview\n### 2. Key Points\n- Key 1\n### 3. Core Concepts\n- Concept 1\n### 4. Important Definitions\n- Def 1",
            "model_used": "gpt-4o-mini",
            "truncated": False,
            "original_length": 500,
            "processed_length": 500,
        }

        response = self.client.post("/summarize", json={"text": "Valid document text"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("Document overview", data["summary"])
        self.assertEqual(data["model_used"], "gpt-4o-mini")

    def test_summarize_endpoint_missing_text(self):
        """Verifies /summarize endpoint returns 400 when text is missing."""
        response = self.client.post("/summarize", json={})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("No text provided", data["error"])

    def test_summarize_endpoint_empty_text(self):
        """Verifies /summarize endpoint returns 400 when text is only whitespace."""
        response = self.client.post("/summarize", json={"text": "   "})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Extracted text is empty", data["error"])


if __name__ == "__main__":
    unittest.main()
