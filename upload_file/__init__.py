import os, json, uuid, requests, azure.functions as func
import logging                                # new

def get_settings():                           # new helper
    ep  = os.getenv("AZURE_OPENAI_ENDPOINT")
    key = os.getenv("AZURE_OPENAI_KEY")
    if not ep or not key:
        logging.error("Missing AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_KEY")
        return None
    return ep, key

def main(req: func.HttpRequest) -> func.HttpResponse:
    settings = get_settings()
    if not settings:
        return func.HttpResponse("Server configuration error", status_code=500)
    EP, KEY = settings
    HDR = {"api-key": KEY}

    file      = req.files.get("file")
    thread_id = req.form.get("thread_id", "")
    vs_id     = req.form.get("vs_id", "")

    if not file:
        return func.HttpResponse("No file", status_code=400)

    # 1· si aún no hay vector store para este hilo, créalo
    if not vs_id:
        vs     = requests.post(f"{EP}/vectorstores", headers=HDR,
                               json={"name": f"vs-{uuid.uuid4()[:8]}"}).json()
        vs_id  = vs["id"]

    # 2· sube el archivo
    up  = requests.post(f"{EP}/files?purpose=assistants", headers=HDR,
                        files={"file": (file.filename, file.stream, file.content_type)}).json()
    fid = up["id"]

    # 3· indexa en ese vector store
    requests.post(f"{EP}/vectorstores/{vs_id}/filebatches",
                  headers=HDR, json={"file_ids": [fid]})

    return func.HttpResponse(
        json.dumps({"file_id": fid, "vs_id": vs_id, "thread_id": thread_id}),
        mimetype="application/json",
    )
