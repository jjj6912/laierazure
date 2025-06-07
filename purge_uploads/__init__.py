import os, requests, datetime as dt, azure.functions as func
import logging                                    # new

def get_settings():                               # new helper
    ep  = os.getenv("AZURE_OPENAI_ENDPOINT")
    key = os.getenv("AZURE_OPENAI_KEY")
    ttl = int(os.getenv("TTL_MIN", "60"))
    if not ep or not key:
        logging.error("Missing AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_KEY")
        return None
    return ep, key, ttl

def main(timer: func.TimerRequest):
    settings = get_settings()
    if not settings:
        return                                  # exit early if misconfigured
    EP, KEY, TTL = settings
    HDR = {"api-key": KEY}

    stores = requests.get(f"{EP}/vectorstores", headers=HDR).json()["data"]
    now    = dt.datetime.utcnow()

    for s in stores:
        if not s["name"].startswith("vs-"):      # deja intacto 'laier-base'
            continue
        age = (now - dt.datetime.fromtimestamp(s["created_at"])).total_seconds()/60
        if age > TTL:
            requests.delete(f"{EP}/vectorstores/{s['id']}", headers=HDR)
