import os, requests, datetime as dt, azure.functions as func

EP, KEY, TTL = (
    os.environ["AZURE_OPENAI_ENDPOINT"],
    os.environ["AZURE_OPENAI_KEY"],
    int(os.environ.get("TTL_MIN", "60"))
)
HDR = {"api-key": KEY}

def main(timer: func.TimerRequest):
    stores = requests.get(f"{EP}/vectorstores", headers=HDR).json()["data"]
    now    = dt.datetime.utcnow()

    for s in stores:
        if not s["name"].startswith("vs-"):      # deja intacto 'laier-base'
            continue
        age = (now - dt.datetime.fromtimestamp(s["created_at"])).total_seconds()/60
        if age > TTL:
            requests.delete(f"{EP}/vectorstores/{s['id']}", headers=HDR)
