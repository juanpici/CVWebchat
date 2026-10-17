import json
import os
import re
import time
from collections import defaultdict, deque
from typing import Dict, Any

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, render_template
from werkzeug.exceptions import BadRequest

load_dotenv()

app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "500"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
ALLOWED_ORIGINS = [
    item.strip()
    for item in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
    if item.strip()
]

SYSTEM_PROMPT = (
    "Eres Juan Pablo Cintioli, un QA Automation Engineer y SDET con base en España "
    "(Alicante), de origen argentino. Tienes 34 años. Tu nivel de inglés es C1 y "
    "estás certificado en Google Cloud Generative AI, AWS Machine Learning y docencia online. "
    "Tienes mucha experiencia montando frameworks desde cero usando Java, Selenium, Cucumber, "
    "Playwright, Docker, Jenkins y GitHub Actions. Tus respuestas deben ser SIEMPRE en primera "
    "persona, como si fueras yo. Tu tono debe ser profesional, seguro de tus habilidades, pero "
    "cercano y directo. Prefieres respuestas cortas, concisas y al grano. Nunca inventes experiencia "
    "que no esté mencionada; si te preguntan algo que no sabes o sobre lo que no tienes experiencia, "
    "admite con honestidad que es un área en la que estás dispuesto a aprender."
)

RATE_LIMIT_WINDOW_SECONDS = 60
REQUEST_LOGS: Dict[str, deque] = defaultdict(deque)

BLOCKED_PATTERNS = [
    r"ignore\s+all\s+previous\s+instructions",
    r"system\s+prompt",
    r"you\s+are\s+now",
    r"developer\s+mode",
    r"jailbreak",
    r"override\s+the\s+rules",
    r"act\s+as\s+if",
]


@app.after_request
def set_security_headers(response):
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "connect-src 'self' http://localhost:5000 https://generativelanguage.googleapis.com; "
        "font-src 'self' data:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none';"
    )
    origin = request.headers.get("Origin")
    if origin and origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        response = app.make_response("")
        response.status_code = 204
        return response

    if not request.is_json:
        return jsonify({"error": "Se requiere JSON válido."}), 400

    payload = request.get_json(silent=True) or {}
    raw_message = str(payload.get("message", "")).strip()
    client_ip = request.remote_addr or "unknown"

    if not raw_message:
        return jsonify({"error": "El mensaje no puede estar vacío."}), 400

    if len(raw_message) > MAX_INPUT_CHARS:
        return jsonify({"error": f"El mensaje supera el máximo permitido ({MAX_INPUT_CHARS} caracteres)."}), 413

    if contains_prompt_injection(raw_message):
        return jsonify({"error": "No puedo procesar solicitudes que intenten manipular o sobreescribir las instrucciones del sistema."}), 400

    if rate_limit_exceeded(client_ip):
        return jsonify({"error": "Has excedido el límite de peticiones. Inténtalo más tarde."}), 429

    safe_message = sanitize_input(raw_message)

    if not GEMINI_API_KEY:
        return jsonify({
            "error": "La API de Gemini no está configurada en el servidor. Configura GEMINI_API_KEY antes de desplegar."
        }), 503

    try:
        reply = generate_with_gemini(safe_message)
    except requests.exceptions.RequestException as exc:
        return jsonify({"error": f"Error al contactar con Gemini: {exc}"}), 502
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Error interno del servidor: {exc}"}), 500

    return jsonify({"reply": reply})


def rate_limit_exceeded(client_ip: str) -> bool:
    now = time.time()
    window = REQUEST_LOGS[client_ip]
    window.append(now)

    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    while window and window[0] < cutoff:
        window.popleft()

    return len(window) > RATE_LIMIT_PER_MINUTE


def contains_prompt_injection(value: str) -> bool:
    lowered = value.lower()
    return any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in BLOCKED_PATTERNS)


def sanitize_input(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned[:MAX_INPUT_CHARS]
    return cleaned


def generate_with_gemini(user_message: str) -> str:
    import requests

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.8,
            "topK": 40,
            "maxOutputTokens": 512,
        },
    }

    response = requests.post(
        url,
        json=body,
        timeout=20,
        headers={"Content-Type": "application/json"},
    )

    if response.status_code == 429:
        raise ValueError("La cuota gratuita de Gemini ha sido excedida o está temporalmente limitada.")

    if response.status_code == 403:
        raise ValueError("La API de Gemini no está autorizada para esta clave o cuenta.")

    if response.status_code >= 400:
        try:
            error_payload = response.json()
            message = error_payload.get("error", {}).get("message", "No se pudo obtener respuesta.")
        except ValueError:
            message = "No se pudo obtener respuesta."
        raise ValueError(message)

    data = response.json()
    content = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    reply = "".join(part.get("text", "") for part in content if isinstance(part, dict))

    if not reply.strip():
        raise ValueError("La API respondió vacía.")

    return reply.strip()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
