from unittest.mock import MagicMock, patch

import server


def test_generate_with_gemini_retries_on_unavailable_model():
    first_response = MagicMock()
    first_response.status_code = 404
    first_response.json.return_value = {
        "error": {"message": "This model is not available."}
    }

    second_response = MagicMock()
    second_response.status_code = 200
    second_response.json.return_value = {
        "candidates": [
            {"content": {"parts": [{"text": "Respuesta de prueba correcta"}]}}
        ]
    }

    with patch.object(server, "MODEL_NAME", "gemini-2.5-flash"), patch.object(
        server,
        "MODEL_FALLBACKS",
        ["gemini-3.8-flash", "gemini-2.0-flash-lite"],
    ), patch.object(server.requests, "post", side_effect=[first_response, second_response]) as mock_post:
        result = server.generate_with_gemini("¿Puedes hablarme de ti?")

    assert result == "Respuesta de prueba correcta"
    assert mock_post.call_count == 2
    assert "gemini-3.8-flash" in mock_post.call_args_list[1][0][0]


def test_generate_with_gemini_continues_incomplete_reply():
    first_response = MagicMock()
    first_response.status_code = 200
    first_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "He trabajado con Selenium y Playwright"}]}}]
    }

    second_response = MagicMock()
    second_response.status_code = 200
    second_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": ", además con Java, Docker y Jenkins en CI/CD."}]}}]
    }

    with patch.object(server, "MODEL_NAME", "gemini-3.8-flash"), patch.object(
        server, "MODEL_FALLBACKS", []
    ), patch.object(server.requests, "post", side_effect=[first_response, second_response]) as mock_post:
        result = server.generate_with_gemini("¿Qué stack usas?")

    assert result == "He trabajado con Selenium y Playwright, además con Java, Docker y Jenkins en CI/CD."
    assert mock_post.call_count == 2


def test_profile_guardrail_accepts_questions_about_documented_experience():
    assert server.is_profile_related_request("¿Qué experiencia tienes con Java?")
    assert server.is_profile_related_request("¿Qué tecnologías aparecen en tu CV?")
    assert server.is_profile_related_request("How did you use Java in your professional experience?")


def test_profile_guardrail_rejects_general_technical_questions():
    assert not server.is_profile_related_request("Explícame Java")
    assert not server.is_profile_related_request("Dame código Java")
    assert not server.is_profile_related_request("¿Cómo creo una clase en Java?")
    assert not server.is_profile_related_request(
        "¿Qué experiencia tienes con Java? Dame un ejemplo de código."
    )
    assert not server.is_profile_related_request("What does CVSS mean?")
    assert not server.is_profile_related_request("What is LinkedIn?")
    assert not server.is_profile_related_request("What are certifications?")


def test_profile_guardrail_rejects_personal_data_even_when_profile_is_mentioned():
    assert not server.is_profile_related_request("¿Qué edad tienes según tu CV?")
    assert not server.is_profile_related_request("¿Cuál es tu email en LinkedIn?")
    assert not server.is_profile_related_request("¿Dónde vives?")
    assert not server.is_profile_related_request("What is your phone number?")


def test_chat_does_not_send_out_of_scope_or_personal_requests_to_gemini():
    with patch.object(server, "generate_with_gemini") as mock_generate:
        with server.app.test_client() as client:
            for message in (
                "Explícame Java",
                "¿Qué edad tienes según tu CV?",
                "¿Cuál es tu email en LinkedIn?",
            ):
                response = client.post("/api/chat", json={"message": message})
                assert response.status_code == 400

    mock_generate.assert_not_called()


def test_chat_allows_documented_experience_questions():
    with patch.object(server, "GEMINI_API_KEY", "test-key"), patch.object(
        server, "generate_with_gemini", return_value="He trabajado con Java."
    ) as mock_generate:
        with server.app.test_client() as client:
            response = client.post(
                "/api/chat",
                json={"message": "¿Qué experiencia tienes con Java?"},
            )

    assert response.status_code == 200
    assert response.json == {"reply": "He trabajado con Java."}
    mock_generate.assert_called_once_with("¿Qué experiencia tienes con Java?")
