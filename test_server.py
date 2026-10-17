from unittest.mock import MagicMock, patch

import server


def test_load_profile_context_combines_only_the_four_linkedin_files(tmp_path):
    expected_sections = []
    for index, filename in enumerate(server.PROFILE_CONTEXT_FILES):
        content = f"Professional fact {index}"
        (tmp_path / filename).write_text(content, encoding="utf-8")
        expected_sections.append(f"### Source: {filename}\n{content}")

    (tmp_path / "linkedin_profile.md").write_text(
        "Legacy profile content must not be loaded.", encoding="utf-8"
    )

    context = server.load_profile_context(str(tmp_path))

    assert context == "\n\n".join(expected_sections)
    assert "Legacy profile content" not in context


def test_load_profile_context_fails_when_a_required_linkedin_file_is_missing(tmp_path):
    for filename in server.PROFILE_CONTEXT_FILES[:-1]:
        (tmp_path / filename).write_text("Professional profile content", encoding="utf-8")

    try:
        server.load_profile_context(str(tmp_path))
    except FileNotFoundError as exc:
        assert server.PROFILE_CONTEXT_FILES[-1] in str(exc)
    else:
        raise AssertionError("Missing LinkedIn source file should fail explicitly")


def test_system_prompt_uses_only_the_four_linkedin_documents(monkeypatch):
    monkeypatch.setattr(server, "PROFILE_CONTEXT", "### Source: linkedin.md\nVerified profile fact")

    prompt = server.build_system_prompt()

    assert "La única fuente autorizada de hechos" in prompt
    assert "no uses conocimientos generales, memoria" in prompt
    assert "Verified profile fact" in prompt


def test_loaded_system_prompt_contains_all_four_linkedin_sources():
    for filename in server.PROFILE_CONTEXT_FILES:
        assert f"### Source: {filename}" in server.SYSTEM_PROMPT


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
    assert server.is_profile_related_request("¿Cuál es tu experiencia laboral?")
    assert server.is_profile_related_request("Cuéntame sobre tu experiencia")
    assert server.is_profile_related_request("Háblame de tu experiencia profesional")
    assert server.is_profile_related_request("Tell me about your work experience")
    assert server.is_profile_related_request("What is your professional background?")
    assert server.is_profile_related_request("¿Qué tecnologías aparecen en tu CV?")
    assert server.is_profile_related_request("How did you use Java in your professional experience?")
    assert server.is_profile_related_request("¿Qué has estudiado?")
    assert server.is_profile_related_request("¿Qué formación tienes?")
    assert server.is_profile_related_request("What did you study?")


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


def test_chat_allows_natural_work_experience_question():
    message = "¿Cuál es tu experiencia laboral?"
    with patch.object(server, "GEMINI_API_KEY", "test-key"), patch.object(
        server, "generate_with_gemini", return_value="La experiencia documentada incluye..."
    ) as mock_generate:
        with server.app.test_client() as client:
            response = client.post("/api/chat", json={"message": message})

    assert response.status_code == 200
    assert response.json == {"reply": "La experiencia documentada incluye..."}
    mock_generate.assert_called_once_with(message)


def test_chat_allows_studies_question_without_broadening_personal_data_access():
    with patch.object(server, "GEMINI_API_KEY", "test-key"), patch.object(
        server, "generate_with_gemini", return_value="La formación documentada incluye FP Grado 3."
    ) as mock_generate:
        with server.app.test_client() as client:
            response = client.post("/api/chat", json={"message": "¿Qué has estudiado?"})

    assert response.status_code == 200
    assert response.json == {
        "reply": "La formación documentada incluye FP Grado 3."
    }
    mock_generate.assert_called_once_with("¿Qué has estudiado?")
