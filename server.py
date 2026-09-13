import base64
import json
import os
from typing import Any
from urllib import error
from urllib import request as urllib_request

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_url_path="", static_folder=".")
CORS(app, resources={r"/*": {"origins": "*"}})
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024


@app.get("/health")
def health() -> Any:
    return jsonify({"ok": True})


@app.route("/")
def index() -> Any:
    return send_from_directory(".", "index.html")


@app.post("/api/extract-text")
def extract_text() -> Any:
    file = request.files.get("file")
    if file is None or file.filename == "":
        return jsonify({"error": "No file uploaded"}), 400

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return jsonify({"error": "GEMINI_API_KEY is not set"}), 500

    file_bytes = file.read()
    mime_type = file.mimetype or "image/png"
    if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
        mime_type = "image/png"

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": "Read the Swedish text in this image and return only the extracted Swedish text. Keep the original wording, line breaks, punctuation and Swedish letters å, ä, ö. Do not add explanations or commentary."
                    },
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(file_bytes).decode("utf-8"),
                        }
                    },
                ]
            }
        ]
    }

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.0-flash:generateContent?key="
        f"{api_key}"
    )

    req = urllib_request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=120) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return jsonify({"error": "Gemini request failed", "details": body}), 502
    except Exception as exc:
        return jsonify({"error": "Failed to call Gemini", "details": str(exc)}), 502

    try:
        parts = response_data["candidates"][0]["content"]["parts"]
        extracted = "".join(part.get("text", "") for part in parts)
        return jsonify({"text": extracted.strip()})
    except (KeyError, IndexError, TypeError):
        return jsonify({"error": "Unexpected Gemini response", "details": response_data}), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=False)
