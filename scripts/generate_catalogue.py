import os
import sys
import subprocess
import time
import requests
from playwright.sync_api import sync_playwright
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def setup_db():
    try:
        print("[Setup] Checking database 'contractguardv2'...")
        # Connect to default 'postgres' database
        conn = psycopg2.connect("postgresql://postgres:helloPeter%402005@localhost:5432/postgres")
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'contractguardv2'")
        exists = cur.fetchone()
        if not exists:
            print("[Setup] Creating database 'contractguardv2'...")
            cur.execute("CREATE DATABASE contractguardv2")
        cur.close()
        conn.close()
        print("[Setup] Initializing database schema...")
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from db.database import engine
        from db import models
        from db import vector_store
        models.Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[Setup] Warning: Could not verify/create DB: {e}")

def start_servers():
    print("[Setup] Starting Backend Server...")
    backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.main:app", "--port", "8000"])
    
    print("[Setup] Starting Frontend Server...")
    frontend = subprocess.Popen(["npm.cmd", "run", "dev", "--", "--port", "5173"], cwd="frontend")
    
    print("[Setup] Waiting for servers to be ready...")
    for _ in range(30):
        try:
            requests.get("http://localhost:8000/healthz")
            break
        except requests.exceptions.ConnectionError:
            time.sleep(1)
            
    time.sleep(5) # Give frontend a bit of time to bundle
    return backend, frontend

def run_playwright():
    print("[Playwright] Starting browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        
        # We need to run seed_demo.py first
        print("[Playwright] Seeding Data...")
        sys.path.append(os.path.dirname(__file__))
        import seed_demo
        seed_demo.run()
        
        print("[Playwright] Navigating to Dashboard...")
        page.goto("http://localhost:5173/")
        
        # Wait for data to load in dashboard
        try:
            page.wait_for_selector(".stat-value", timeout=15000)
            time.sleep(5) # Wait for chart animations and data rendering
        except Exception as e:
            print(f"[Playwright] Dashboard load timeout: {e}")
        
        # Take full page screenshot
        artifact_dir = r"C:\Users\tarun\.gemini\antigravity\brain\65d63f7c-a5bb-4b4d-add5-484a42507c24"
        os.makedirs(artifact_dir, exist_ok=True)
        
        ss_path = os.path.join(artifact_dir, "dashboard_overview.png")
        page.screenshot(path=ss_path, full_page=True)
        print(f"[Playwright] Screenshot saved to {ss_path}")
        
        browser.close()
        return ss_path

if __name__ == "__main__":
    setup_db()
    bg, fg = start_servers()
    ss_path = ""
    try:
        ss_path = run_playwright()
    finally:
        print("[Setup] Cleaning up servers...")
        bg.terminate()
        fg.terminate()
        print(f"[Success] Catalogue assets generated! -> {ss_path}")
