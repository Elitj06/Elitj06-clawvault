"""
ClawVault — Speech-to-Text via Deepgram REST API
=================================================
Transcribes audio using Deepgram nova-3 (PT-BR).
Uses raw HTTP to avoid SDK version issues.
"""

import os
import logging
import httpx

logger = logging.getLogger(__name__)

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")


async def transcribe_audio(audio_data: bytes, mime_type: str = "audio/webm") -> dict:
    """Transcribe audio bytes using Deepgram nova-3 (PT-BR optimized).

    Args:
        audio_data: Raw audio bytes to transcribe.
        mime_type: MIME type of the audio (default: audio/webm).

    Returns:
        dict: {text: str, confidence: float, duration: float, error: str (on failure)}
    """
    if not DEEPGRAM_API_KEY or DEEPGRAM_API_KEY.startswith("placeholder"):
        return {
            "text": "",
            "confidence": 0.0,
            "duration": 0.0,
            "error": "DEEPGRAM_API_KEY not configured",
        }
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/listen",
                headers={
                    "Authorization": f"Token {DEEPGRAM_API_KEY}",
                    "Content-Type": mime_type,
                },
                params={
                    "model": "nova-3",
                    "language": "pt-BR",
                    "smart_format": "true",
                    "punctuate": "true",
                },
                content=audio_data,
            )
            
            if resp.status_code != 200:
                logger.error(f"Deepgram API error: {resp.status_code} {resp.text[:200]}")
                return {
                    "text": "",
                    "confidence": 0.0,
                    "duration": 0.0,
                    "error": f"Deepgram API {resp.status_code}",
                }
            
            data = resp.json()
            results = data.get("results", {})
            channels = results.get("channels", [])
            
            if channels:
                alternatives = channels[0].get("alternatives", [])
                if alternatives:
                    alt = alternatives[0]
                    return {
                        "text": alt.get("transcript", "").strip(),
                        "confidence": alt.get("confidence", 0.0),
                        "duration": results.get("duration", 0.0),
                    }
            
            return {"text": "", "confidence": 0.0, "duration": 0.0}
    
    except Exception as e:
        logger.error(f"Deepgram transcription failed: {e}")
        return {
            "text": "",
            "confidence": 0.0,
            "duration": 0.0,
            "error": str(e),
        }
