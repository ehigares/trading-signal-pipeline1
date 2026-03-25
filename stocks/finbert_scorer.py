"""
finbert_scorer.py — Shadow sentiment scorer using FinBERT.
Runs alongside keyword classifier for comparison only.
Does not affect signal selection until Phase 2 deployment.
"""

import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SHADOW_LOG = SCRIPT_DIR / "finbert_shadow_log.json"

# Try to import transformers — fail gracefully if not installed
try:
    from transformers import (BertTokenizer,
                              BertForSequenceClassification)
    import torch
    _MODEL_LOADED = False
    _tokenizer = None
    _model = None
    FINBERT_AVAILABLE = True
except ImportError:
    FINBERT_AVAILABLE = False

def _load_model():
    """Load FinBERT model on first call (lazy loading)."""
    global _MODEL_LOADED, _tokenizer, _model
    if _MODEL_LOADED:
        return True
    if not FINBERT_AVAILABLE:
        return False
    try:
        _tokenizer = BertTokenizer.from_pretrained(
            "ProsusAI/finbert")
        _model = BertForSequenceClassification.from_pretrained(
            "ProsusAI/finbert")
        _model.eval()
        _MODEL_LOADED = True
        return True
    except Exception as e:
        print(f"  [FINBERT] Model load failed: {e}")
        return False

def score_headline(headline: str, summary: str = "") -> dict:
    """Score a headline using FinBERT.
    Returns dict with sentiment, score (-1 to 1), confidence."""
    if not _load_model():
        return {"sentiment": "unavailable", "score": 0.0,
                "confidence": 0.0}
    try:
        text = f"{headline} {summary}".strip()[:512]
        inputs = _tokenizer(text, return_tensors="pt",
                           truncation=True, max_length=512)
        with torch.no_grad():
            outputs = _model(**inputs)
        probs = torch.softmax(outputs.logits, dim=1)[0]
        # FinBERT labels: 0=positive, 1=negative, 2=neutral
        positive = float(probs[0])
        negative = float(probs[1])
        neutral = float(probs[2])

        # Composite score: positive - negative (-1 to +1)
        score = round(positive - negative, 4)
        confidence = round(max(positive, negative, neutral), 4)

        if positive > negative and positive > neutral:
            sentiment = "positive"
        elif negative > positive and negative > neutral:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return {
            "sentiment": sentiment,
            "score": score,
            "confidence": confidence,
            "positive_prob": round(positive, 4),
            "negative_prob": round(negative, 4),
            "neutral_prob": round(neutral, 4),
        }
    except Exception as e:
        return {"sentiment": "error", "score": 0.0,
                "confidence": 0.0, "error": str(e)}

def log_shadow_comparison(ticker: str, headline: str,
                           keyword_type: str,
                           keyword_score: int,
                           finbert_result: dict):
    """Append a shadow comparison entry to finbert_shadow_log.json."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    entry = {
        "timestamp": datetime.now(
            ZoneInfo("America/New_York")
        ).isoformat(timespec="seconds"),
        "ticker": ticker,
        "headline": headline[:200],
        "keyword_type": keyword_type,
        "keyword_score": keyword_score,
        "finbert_sentiment": finbert_result.get("sentiment"),
        "finbert_score": finbert_result.get("score"),
        "finbert_confidence": finbert_result.get("confidence"),
    }
    try:
        if SHADOW_LOG.exists():
            with open(SHADOW_LOG, "r") as f:
                log = json.load(f)
        else:
            log = []
        log.append(entry)
        # Keep last 500 entries only
        log = log[-500:]
        with open(SHADOW_LOG, "w") as f:
            json.dump(log, f, indent=2)
    except Exception:
        pass  # Shadow logging never crashes pipeline
