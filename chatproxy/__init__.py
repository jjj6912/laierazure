import os, time, json, requests, datetime as dt, azure.functions as func
from azure.data.tables import TableClient
from azure.core.exceptions import ResourceNotFoundError

EP  = os.getenv("ENDPOINT_URL")
KEY = os.getenv("AZURE_OPENAI_API_KEY")
DEP = os.getenv("DEPLOYMENT_NAME")           # gpt-4o-mini
HDR = {"api-key": KEY}

# --- cuota 600 respuestas / mes -----------
tbl = TableClient.from_connection_string(os.getenv("AzureWebJobsStorage"),"quota")
QUOTA = 600
def inc(uid):
    month = dt.datetime.utcnow().strftime("%Y-%m")
    try:
        row = tbl.get_entity(month, uid)
        count = row["count"]
        if count >= QUOTA:
            return False
        row["count"] = count + 1
        tbl.update_entity(row, mode="Merge")
    except ResourceNotFoundError:
        # This will only run if the entity does not exist
        tbl.create_entity({"PartitionKey": month, "RowKey": uid, "count": 1})
    return True
# ------------------------------------------

def search_ctx(vs, q):
    sr = requests.post(
        f"{EP}/openai/vectorstores/{vs}/similarity_search?api-version=2025-01-01-preview",
        headers=HDR, json={"query": q, "top_k": 4}
    ).json()
    ctx = "\n\n".join([d["text"] for d in sr["data"]])
    return ctx

def main(req: func.HttpRequest):
    b = req.get_json()
    user = b.get("user_id", "anon")
    if not inc(user):
        return func.HttpResponse(
            json.dumps({"reply": "Límite 600/mes alcanzado"}),
            403,
            mimetype="application/json"
        )

    vs = b.get("vs_id")
    q = b["message"]
    msgs = [
        {"role": "system", "content": "Eres LAIER, asistente legal experto en derecho español."}
    ]
    if vs:
        msgs.append({"role": "system", "content": "Contexto:\n" + search_ctx(vs, q)})
    msgs.append({"role": "user", "content": q})

    r = requests.post(
        f"{EP}/openai/deployments/{DEP}/chat/completions?api-version=2025-01-01-preview",
        headers=HDR, json={"messages": msgs, "max_tokens": 800}
    ).json()
    ans = r["choices"][0]["message"]["content"]
    return func.HttpResponse(
        json.dumps({"reply": ans, "vs_id": vs}),
        mimetype="application/json"
    )
