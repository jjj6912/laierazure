import os, logging, datetime as dt
import azure.functions as func
from openai import AzureOpenAI

API_VERSION = "2024-05-01-preview"

def get_settings():
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
        return
    EP, KEY, TTL = settings

    try:
        client = AzureOpenAI(api_version=API_VERSION, azure_endpoint=EP, api_key=KEY)
        
        now = dt.datetime.now(dt.timezone.utc)
        
        # Obtener todos los vector stores
        all_stores = client.beta.vector_stores.list()

        for store in all_stores:
            if not store.name or not store.name.startswith("vs-"):
                continue
            
            store_creation_time = dt.datetime.fromtimestamp(store.created_at, tz=dt.timezone.utc)
            age_minutes = (now - store_creation_time).total_seconds() / 60
            
            if age_minutes > TTL:
                logging.info(f"Deleting expired vector store {store.id} (age: {age_minutes:.2f} mins)")
                client.beta.vector_stores.delete(vector_store_id=store.id)

    except Exception as e:
        logging.error(f"Error in purge_uploads: {e}")
