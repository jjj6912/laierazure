import os, json, time, requests, azure.functions as func
import logging                                  # new

def get_settings():                             # new helper
    ep  = os.getenv("AZURE_OPENAI_ENDPOINT")
    key = os.getenv("AZURE_OPENAI_KEY")
    ag   = os.getenv("AGENT_ID")
    missing = [n for n, v in {
        "AZURE_OPENAI_ENDPOINT": ep,
        "AZURE_OPENAI_KEY": key,
        "AGENT_ID": ag,
    }.items() if not v]
    if missing:
        logging.error(f"Missing environment variables: {', '.join(missing)}")
        return None
    return ep, key, ag

def wait(url, hdr):
    while True:
        run = requests.get(url, headers=hdr).json()
        if run["status"] in ("completed", "failed"):
            return
        time.sleep(0.7)

def main(req: func.HttpRequest) -> func.HttpResponse:
    settings = get_settings()
    if not settings:                             # return 500 if misconfigured
        return func.HttpResponse("Server configuration error", status_code=500)
    EP, KEY, AG = settings
    HDR = {"api-key": KEY, "Content-Type": "application/json"}

    b        = req.get_json()
    msg      = b.get("message")
    thread   = b.get("thread_id")
    vs_id    = b.get("vs_id")

    if not msg:
        return func.HttpResponse("Missing message", status_code=400)

    if not thread:
        thread = requests.post(f"{EP}/threads", headers=HDR, json={}).json()["id"]

    requests.post(f"{EP}/threads/{thread}/messages",
                  headers=HDR, json={"role": "user", "content": msg})

    run = requests.post(f"{EP}/threads/{thread}/runs", headers=HDR, json={
        "assistant_id": AG,
        "tool_resources": {"file_search": {"vector_store_ids": [vs_id]}} if vs_id else {}
    }).json()

    wait(f"{EP}/threads/{thread}/runs/{run['id']}", HDR)

    last  = requests.get(f"{EP}/threads/{thread}/messages", headers=HDR).json()["data"][0]
    reply = last["content"][0]["text"]["value"]

    return func.HttpResponse(
        json.dumps({"reply": reply, "thread_id": thread, "vs_id": vs_id}),
        mimetype="application/json",
    )
