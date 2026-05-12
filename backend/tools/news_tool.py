import os
import json
import httpx
from config import settings

class NewsTool:
    def __init__(self):
        self.api_key = settings.gnews_api_key
        self.base_url = "https://gnews.io/api/v4/search"

    def get_entity_news(self, entity_name: str) -> dict:
        """Fetch real news using GNews API with adverse keyword filtering."""
        # Check for manual data override first
        manual = os.environ.get("NEWS_MANUAL_DATA")
        if manual:
            try:
                articles = json.loads(manual)
                return {
                    "total_articles_analyzed": len(articles),
                    "adverse_signals_found": len(articles),
                    "signals": articles
                }
            except Exception:
                pass

        if not self.api_key:
            return {"total_articles_analyzed": 0, "adverse_signals_found": 0, "signals": [], "note": "No API key"}

        try:
            # Search for the entity with risk-related keywords
            query = f'"{entity_name}" AND (default OR "legal dispute" OR bankruptcy OR "insolvency" OR "delay" OR penalty)'
            params = {
                "q": query,
                "token": self.api_key,
                "lang": "en",
                "max": 5
            }
            resp = httpx.get(self.base_url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                articles = data.get("articles", [])
                
                # Simple keyword matching for "adverse signals"
                adverse_keywords = ["default", "dispute", "court", "penalty", "delay", "violation"]
                signals = []
                for art in articles:
                    content = (art.get("title", "") + " " + art.get("description", "")).lower()
                    matched = [k for k in adverse_keywords if k in content]
                    if matched:
                        signals.append({
                            "title": art.get("title"),
                            "url": art.get("url"),
                            "published_at": art.get("publishedAt"),
                            "matched_keywords": matched
                        })

                return {
                    "total_articles_analyzed": len(articles),
                    "adverse_signals_found": len(signals),
                    "signals": signals
                }
            else:
                print(f"[NewsTool] GNews returned {resp.status_code}: {resp.text}")
                return {"total_articles_analyzed": 0, "adverse_signals_found": 0, "signals": []}

        except Exception as e:
            print(f"[NewsTool] Error: {e}")
            return {"total_articles_analyzed": 0, "adverse_signals_found": 0, "signals": []}
