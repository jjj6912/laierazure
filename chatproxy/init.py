import os, json, time, requests, azure.functions as func

EP  = os.environ["AZURE_OPENAI_ENDPOINT"]
KEY = os.environ["AZURE_OPENAI_KEY"]
AG  = os.environ["AGENT_ID"]
HDR = {"api-key": KEY, "Content-Type": "application/json"}

def wait(url):
    while True:
        run = requests.get(url, headers=HDR).json()
        if run["status"] in ("completed", "failed"):
            return
        time.sleep(0.7)

def main(req: func.HttpRequest) -> func.HttpResponse:
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

    wait(f"{EP}/threads/{thread}/runs/{run['id']}")

    last  = requests.get(f"{EP}/threads/{thread}/messages", headers=HDR).json()["data"][0]
    reply = last["content"][0]["text"]["value"]

    return func.HttpResponse(
        json.dumps({"reply": reply, "thread_id": thread, "vs_id": vs_id}),
        mimetype="application/json"
    )
