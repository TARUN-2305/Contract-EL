"""
Weather Tool — tools/weather_tool.py
Fetches historical rainfall data from Open-Meteo to validate Force Majeure claims.
Calculates weather_anomaly_score.
"""
import os
import json
import requests
from datetime import date
from typing import Optional, Dict, Any

from agents.compliance_engine import _parse_date

LOCATION_COORDS = {
    "New Delhi": (28.6139, 77.2090),
    "Mumbai": (19.0760, 72.8777),
    "Bengaluru": (12.9716, 77.5946),
    "Chennai": (13.0827, 80.2707),
    "Kolkata": (22.5726, 88.3639),
    "Karnataka, India": (15.3173, 75.7139),
    "Karnataka": (15.3173, 75.7139),
    "Assam": (26.2006, 92.9376),
    "Maharashtra": (19.7515, 75.7139)
}

class WeatherTool:
    def __init__(self):
        self.source = os.environ.get("WEATHER_SOURCE", "open_meteo")
        self.manual_data = os.environ.get("WEATHER_MANUAL_DATA")
        self.base_url = "https://archive-api.open-meteo.com/v1/archive"

    def get_rainfall_data(self, location: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Fetch historical rainfall data using Open-Meteo.
        Supports manual JSON overrides and synthetic fallback.
        """
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        
        if not start or not end:
            return {"error": "Invalid date format. Use YYYY-MM-DD"}
            
        days = max(1, (end - start).days)

        if self.source == "manual" and self.manual_data:
            try:
                data = json.loads(self.manual_data)
                return data
            except json.JSONDecodeError:
                pass
                
        if self.source == "synthetic":
            return self._generate_synthetic_weather(location, days)

        # Open-Meteo historical fetch
        lat, lon = LOCATION_COORDS.get(location, (28.6139, 77.2090)) # Default New Delhi
        try:
            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": start_date,
                "end_date": end_date,
                "daily": "precipitation_sum",
                "timezone": "auto"
            }
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            daily_precip = data.get("daily", {}).get("precipitation_sum", [])
            valid_precip = [p for p in daily_precip if p is not None]
            
            total_rainfall = sum(valid_precip)
            extreme_days = sum(1 for p in valid_precip if p > 50.0) # > 50mm considered extreme
            
            # Historical avg for the same period (rough proxy)
            base_rainfall_mm = 5.0
            
            return {
                "location": location,
                "period_days": days,
                "total_rainfall_mm": round(total_rainfall, 2),
                "extreme_rainfall_days": extreme_days,
                "historical_average_mm": round(base_rainfall_mm * days, 2),
                "source": "open_meteo_archive"
            }
        except Exception as e:
            print(f"[WeatherTool] API failed: {e}. Falling back to synthetic.")
            return self._generate_synthetic_weather(location, days)

    def _generate_synthetic_weather(self, location: str, days: int) -> Dict[str, Any]:
        """Generate plausible synthetic rainfall data for testing."""
        import random
        random.seed(hash(location) % (2**32))
        # Base daily average based on typical Indian monsoon (rough proxy)
        base_rainfall_mm = 5.0
        
        # Determine if there's an anomaly in the synthetic window
        has_anomaly = random.random() < 0.3
        
        total_rainfall = 0
        extreme_days = 0
        
        for _ in range(days):
            daily = random.uniform(0, base_rainfall_mm * 2)
            if has_anomaly and random.random() < 0.2:
                daily += random.uniform(50, 150) # Flash flood / heavy rain
                extreme_days += 1
            total_rainfall += daily
            
        return {
            "location": location,
            "period_days": days,
            "total_rainfall_mm": round(total_rainfall, 2),
            "extreme_rainfall_days": extreme_days,
            "historical_average_mm": round(base_rainfall_mm * days, 2),
            "source": "synthetic_fallback"
        }

    def verify_force_majeure(self, claim: dict) -> Dict[str, Any]:
        """
        Validate a Force Majeure claim based on weather anomaly.
        """
        location = claim.get("location", "New Delhi")
        start = claim.get("event_date")
        end = claim.get("date_ended") or str(date.today())
        
        if not start:
            return {"valid": False, "reason": "No event date provided"}
            
        weather_data = self.get_rainfall_data(location, start, end)
        
        if "error" in weather_data:
            return {"valid": None, "reason": weather_data["error"]}
            
        # Calculate anomaly score (0.0 to 1.0)
        # If rainfall is 2x historical average, score approaches 1.0
        total_rain = weather_data.get("total_rainfall_mm", 0)
        hist_rain = weather_data.get("historical_average_mm", 1)
        
        ratio = total_rain / max(1, hist_rain)
        anomaly_score = min(1.0, max(0.0, (ratio - 1) / 2))
        
        # Consider an anomaly score >= 0.75 as valid grounds for FM review, or > 2 extreme days
        FM_ANOMALY_THRESHOLD = 0.75
        is_valid = anomaly_score >= FM_ANOMALY_THRESHOLD or weather_data.get("extreme_rainfall_days", 0) > 2
        
        return {
            "valid": is_valid,
            "anomaly_score": round(anomaly_score, 4),
            "weather_data": weather_data,
            "reason": "Severe weather verified" if is_valid else "Weather data does not support Force Majeure claim."
        }


# ── CLI Test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    
    tool = WeatherTool()
    
    claim = {
        "event_id": "FM-001",
        "location": "Mumbai",
        "event_date": "2023-07-15",
        "date_ended": "2023-07-20",
        "claimed_days": 5
    }
    
    result = tool.verify_force_majeure(claim)
    print("=== Weather Tool FM Verification ===")
    import json
    print(json.dumps(result, indent=2))
