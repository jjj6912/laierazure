import azure.functions as func
import os, mimetypes, logging

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../wwwroot"))  # new

def main(req: func.HttpRequest) -> func.HttpResponse:
    filepath = req.route_params.get("filepath")
    if not filepath:
        logging.warning("File path not provided in request.")
        return func.HttpResponse("File path not provided", status_code=400)

    full_path = os.path.abspath(os.path.join(ROOT, filepath))
    if not full_path.startswith(ROOT):                                           # new check
        logging.warning(f"Path traversal attempt: {filepath}")
        return func.HttpResponse("Forbidden", status_code=403)

    logging.info(f"Attempting to serve file: {full_path}")

    file_exists = os.path.exists(full_path) and os.path.isfile(full_path)
    logging.info(f"File exists: {file_exists}")

    if file_exists:
        try:
            with open(full_path, "rb") as f:
                content = f.read()
            mime_type, _ = mimetypes.guess_type(full_path)
            logging.info(f"Successfully served file: {full_path} with MIME type: {mime_type}")
            return func.HttpResponse(content, mimetype=mime_type or "application/octet-stream")
        except Exception as e:
            logging.error(f"Error serving file {full_path}: {e}")
            return func.HttpResponse("Error serving file", status_code=500)
    else:
        logging.warning(f"File not found: {full_path}")
        return func.HttpResponse("File not found", status_code=404)
