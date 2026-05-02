"""
News Tool — tools/news_tool.py
Fetches latest news for a specific entity (Contractor) using GNews to detect early warning signals.
"""
import os
import json
import requests
from datetime import date, timedelta
from typing import Dict, Any, List

class NewsTool:
    def __init__(self):
        self.api_key = os.environ.get("GNEWS_API_KEY")
        self.override_file = os.environ.get("NEWS_OVERRIDE_FILE")
        self.base_url = "https://gnews.io/api/v4/search"
        
        # Risk keywords for the Indian construction sector
        self.risk_keywords = [
            "insolvency", "NCLT", "bankrupt", "fraud", "default", 
            "CBI", "ED raid", "blacklist", "debarred", "liquidation",
            "delayed salary", "strike"
        ]

    def get_entity_news(self, entity_name: str, days_back: int = 30) -> Dict[str, Any]:
        """
        Fetch recent news for an entity and flag risk signals.
        If no API key is provided, returns synthetic data for testing.
        """
        if self.override_file and os.path.exists(self.override_file):
            try:
                with open(self.override_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[NewsTool] Failed to read override file: {e}")

        if not self.api_key:
            return self._generate_synthetic_news(entity_name)
            
        try:
            query = f'"{entity_name}"'
            
            params = {
                "q": query,
                "lang": "en",
                "max": 10,
                "token": self.api_key
            }
            
            response = requests.get(self.base_url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return self._analyze_articles(data.get("articles", []))
            else:
                return {"error": f"GNews error: {response.status_code} - {response.text}"}
                
        except Exception as e:
            return {"error": f"News fetch error: {str(e)}"}

    def _analyze_articles(self, articles: List[dict]) -> Dict[str, Any]:
        """Analyze fetched articles for risk signals."""
        risk_signals = []
        
        for article in articles:
            text = (article.get("title", "") + " " + article.get("description", "")).lower()
            found_keywords = [kw for kw in self.risk_keywords if kw.lower() in text]
            
            if found_keywords:
                risk_signals.append({
                    "title": article.get("title"),
                    "source": article.get("source", {}).get("name"),
                    "published_at": article.get("publishedAt"),
                    "url": article.get("url"),
                    "matched_keywords": found_keywords
                })
                
        # Calculate a basic risk score based on frequency of adverse news
        score = min(1.0, len(risk_signals) * 0.2)
        
        return {
            "total_articles_analyzed": len(articles),
            "adverse_signals_found": len(risk_signals),
            "risk_score": round(score, 2),
            "signals": risk_signals,
            "source": "gnews"
        }

    def _generate_synthetic_news(self, entity_name: str) -> Dict[str, Any]:
        """Generate plausible synthetic news for testing."""
        import random
        
        is_risky = random.random() < 0.2 # 20% chance of generating adverse news
        
        if not is_risky:
            return {
                "total_articles_analyzed": 15,
                "adverse_signals_found": 0,
                "risk_score": 0.0,
                "signals": [],
                "source": "synthetic_fallback"
            }
            
        signals = [
            {
                "title": f"NCLT admits insolvency plea against {entity_name}",
                "source": "Economic Times",
                "published_at": str(date.today() - timedelta(days=2)),
                "url": "https://example.com/news/1",
                "matched_keywords": ["insolvency", "NCLT"]
            },
            {
                "title": f"Workers of {entity_name} protest over delayed salary",
                "source": "Business Standard",
                "published_at": str(date.today() - timedelta(days=5)),
                "url": "https://example.com/news/2",
                "matched_keywords": ["delayed salary", "strike"]
            }
        ]
        
        return {
            "total_articles_analyzed": 42,
            "adverse_signals_found": 2,
            "risk_score": 0.8,
            "signals": signals,
            "source": "synthetic_fallback"
        }


# ── CLI Test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    
    tool = NewsTool()
    
    entity = "XYZ Constructions Pvt. Ltd."
    result = tool.get_entity_news(entity)
    
    print("=== News Tool Risk Analysis ===")
    import json
    print(json.dumps(result, indent=2))
