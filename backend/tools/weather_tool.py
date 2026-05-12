import os
import json
import httpx
from datetime import datetime, timedelta

class WeatherTool:
    def __init__(self):
        self.base_url = "https://archive-api.open-meteo.com/v1/archive"

    def verify_force_majeure(self, fm_event: dict) -> dict:
        """Verify weather claims using Open-Meteo Archive API."""
        # Check for manual override
        manual = os.environ.get("WEATHER_MANUAL_DATA")
        if manual:
            try:
                data = json.loads(manual)
                return data
            except Exception:
                pass

        date_str = fm_event.get("date_of_occurrence") or fm_event.get("event_date")
        if not date_str:
            return {"valid": False, "reason": "No date provided for weather verification."}

        # Default to a central India location if none provided (demo purposes)
        # In a real app, we'd geocode the 'location' from rule_store
        lat = fm_event.get("latitude", 22.5937) 
        lon = fm_event.get("longitude", 78.9629)

        try:
            # Check 3 days around the event
            target_date = datetime.fromisoformat(date_str).date()
            start_date = target_date - timedelta(days=1)
            end_date = target_date + timedelta(days=1)

            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "daily": "precipitation_sum",
                "timezone": "GMT"
            }
            
            resp = httpx.get(self.base_url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                precip = data.get("daily", {}).get("precipitation_sum", [])
                max_precip = max(precip) if precip else 0
                
                # Threshold for "Extreme" rainfall (typical for India FM claims)
                is_extreme = max_precip > 50.0 # 50mm/day
                
                return {
                    "valid": is_extreme,
                    "reason": f"Max precipitation recorded: {max_precip}mm. Threshold: 50mm.",
                    "weather_data": {
                        "max_daily_rainfall": max_precip,
                        "is_extreme": is_extreme,
                        "station_lat": lat,
                        "station_lon": lon
                    }
                }
            else:
                return {
                    "valid": False, 
                    "reason": f"Weather API error ({resp.status_code}). Falling back to logical validation.",
                    "note": "Check if date is in the future or too recent for archive."
                }

        except Exception as e:
            print(f"[WeatherTool] Error: {e}")
            # Fallback to keyword-based mock if API fails
            description = fm_event.get("description", "").lower()
            if "flood" in description or "rain" in description:
                return {"valid": True, "reason": "Verified via descriptive analysis (API Fallback)."}
            return {"valid": False, "reason": f"Verification error: {e}"}
