import os, datetime as dt, requests

EP  = os.getenv("ENDPOINT_URL")
KEY = os.getenv("AZURE_OPENAI_API_KEY")
HDR = {"api-key": KEY}
TTL = int(os.getenv("TTL_MIN","60"))

def main(mytimer):
    now=dt.datetime.utcnow()
    lst=requests.get(f"{EP}/openai/vectorstores?api-version=2025-01-01-preview",
                     headers=HDR).json()["data"]
    for s in lst:
        if not s["name"].startswith("vs-"): continue
        age=(now-dt.datetime.fromtimestamp(s["created_at"])).total_seconds()/60
        if age>TTL:
            requests.delete(f"{EP}/openai/vectorstores/{s['id']}?api-version=2025-01-01-preview",
                            headers=HDR)
