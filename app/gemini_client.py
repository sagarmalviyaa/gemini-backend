import google.generativeai as genai
from app.config import settings
import logging
from typing import List, Dict, Optional
import os

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        if settings.gemini_api_key:
            logger.info(settings.gemini_api_key)
            genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash-lite')
        else:
            self.model = None
            logger.warning("Gemini API key not configured")

    def generate_response(self, content: Optional[str] = None, context: Optional[List[Dict]] = None) -> str:
        """Generate response using Gemini API. Prefers context, falls back to plain content."""
        if not self.model:
            return "Gemini API is not configured. Please add your API key to use AI features."
        try:
            if context and isinstance(context, list) and context:
                # Ensure context is non-empty and list of dicts in Gemini format
                logger.info(f"[GEMINI] Using chat context: {context}")
                response = self.model.generate_content(context)
            elif content and isinstance(content, str) and content.strip():
                logger.info(f"[GEMINI] Using content only: {content!r}")
                response = self.model.generate_content(content)
            else:
                logger.error("[GEMINI] Called with no valid input (no context, no content).")
                return "[No input provided to Gemini.]"
            # Extract AI text from the response object
            text = getattr(response, "text", None)
            if text and text.strip():
                return text
            return "[No text received from Gemini AI.]"
        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            return "Sorry, the AI could not process your message due to a technical error. Please try again later."

# Instantiate singleton
gemini_client = GeminiClient()
