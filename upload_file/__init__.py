import os, uuid, json, requests, azure.functions as func

EP  = os.getenv("ENDPOINT_URL")            # https://laiertest2-resource.openai.azure.com/
KEY = os.getenv("AZURE_OPENAI_API_KEY")
HDR = {"api-key": KEY}

def make_vs():
    r = requests.post(f"{EP}/openai/vectorstores?api-version=2025-01-01-preview",
                      headers=HDR,
                      json={"name":f"vs-{uuid.uuid4()[:8]}"}).json()
    return r["id"]

def main(req: func.HttpRequest):
    f = req.files.get("file")
    vs = req.form.get("vs_id") or make_vs()
    if not f: return func.HttpResponse("no file",400)

    up = requests.post(f"{EP}/openai/files?api-version=2025-01-01-preview&purpose=assistants",
                       headers=HDR,
                       files={"file":(f.filename,f.stream,f.content_type)}).json()

    requests.post(f"{EP}/openai/vectorstores/{vs}/filebatches?api-version=2025-01-01-preview",
                  headers=HDR,json={"file_ids":[up["id"]]})
    return func.HttpResponse(json.dumps({"vs_id":vs}),mimetype="application/json")
