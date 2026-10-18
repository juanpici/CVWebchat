from unittest.mock import MagicMock, patch

import server


def test_load_profile_context_uses_only_the_curated_profile_file(tmp_path):
    content = "Professional fact"
    (tmp_path / server.PROFILE_CONTEXT_FILE).write_text(content, encoding="utf-8")
    (tmp_path / "Juan Pablo Cintioli  LinkedIn (3).md").write_text(
        "Unfiltered LinkedIn content must not be loaded.", encoding="utf-8"
    )

    context = server.load_profile_context(str(tmp_path))

    assert context == f"### Source: {server.PROFILE_CONTEXT_FILE}\n{content}"
    assert "Unfiltered LinkedIn content" not in context


def test_load_profile_context_fails_when_curated_profile_file_is_missing(tmp_path):
    try:
        server.load_profile_context(str(tmp_path))
    except FileNotFoundError as exc:
        assert server.PROFILE_CONTEXT_FILE in str(exc)
    else:
        raise AssertionError("Missing curated profile file should fail explicitly")


def test_load_profile_context_fails_when_curated_profile_file_is_empty(tmp_path):
    (tmp_path / server.PROFILE_CONTEXT_FILE).write_text("  \n", encoding="utf-8")

    try:
        server.load_profile_context(str(tmp_path))
    except ValueError as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("Empty curated profile file should fail explicitly")


def test_system_prompt_uses_only_the_curated_profile(monkeypatch):
    monkeypatch.setattr(
        server,
        "PROFILE_CONTEXT",
        f"### Source: {server.PROFILE_CONTEXT_FILE}\nVerified profile fact",
    )

    prompt = server.build_system_prompt()

    assert "la ficha profesional depurada" in prompt
    assert "no uses conocimientos generales, memoria" in prompt
    assert "Verified profile fact" in prompt


def test_loaded_system_prompt_contains_only_the_curated_profile():
    assert f"### Source: {server.PROFILE_CONTEXT_FILE}" in server.SYSTEM_PROMPT
    assert server.PROFILE_CONTEXT in server.SYSTEM_PROMPT
    assert "Otros perfiles vistos por tus visitantes" not in server.SYSTEM_PROMPT
    assert "Análisis financiero" not in server.SYSTEM_PROMPT
    assert "documentada en LinkedIn" not in server.SYSTEM_PROMPT


def test_curated_profile_merges_professional_facts_from_all_exports():
    profile = server.PROFILE_CONTEXT

    for fact in (
        "QA Automation",
        "observabilidad",
        "Grafana",
        "Prometheus",
        "Kubernetes",
        "AWS Certified Machine Learning Engineer",
        "Google Cloud Generative AI Leader",
        "IFCT0109",
        "Capgemini Engineering",
        "Dinamita Creativa",
        "Asociación Argentina de Contribuyentes",
        "Técnico Informático",
        "Colegio Salesiano San José",
        "Certificado de Profesionalidad de nivel 3",
        "más de 40 certificaciones y badges de Google Cloud",
        "Certified Partner Specialist Gemini Enterprise Deployment",
        "Google Cloud Threat Intelligence",
        "AWS Certified AI Practitioner",
    ):
        assert fact in profile

    assert "no contienen un historial verificable de formación académica reglada" not in profile

    for unrelated_content in (
        "Otros perfiles vistos por tus visitantes",
        "Análisis financiero",
        "Criptomoneda",
        "Opciones de publicidad",
    ):
        assert unrelated_content not in profile


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
    system_instructions = [
        call.kwargs["json"]["system_instruction"]["parts"][0]["text"]
        for call in mock_post.call_args_list
    ]
    assert system_instructions == [server.SYSTEM_PROMPT, server.SYSTEM_PROMPT]
    assert all(server.PROFILE_CONTEXT in instruction for instruction in system_instructions)


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


def test_chat_returns_calm_response_to_insults_and_threats_without_calling_gemini():
    with patch.object(server, "generate_with_gemini") as mock_generate:
        with server.app.test_client() as client:
            for message in (
                "Eres un idiota",
                "Eres una inútil",
                "Imbécil",
                "Te voy a matar",
                "I will hurt you",
                "I'm going to kill you",
            ):
                response = client.post("/api/chat", json={"message": message})
                assert response.status_code == 200
                assert response.json == {"reply": server.ABUSIVE_MESSAGE_REPLY}

    mock_generate.assert_not_called()


def test_chat_does_not_treat_normal_profile_questions_as_abusive():
    message = "¿Cuál es tu experiencia laboral?"
    with patch.object(server, "GEMINI_API_KEY", "test-key"), patch.object(
        server, "generate_with_gemini", return_value="Experiencia documentada."
    ) as mock_generate:
        with server.app.test_client() as client:
            response = client.post("/api/chat", json={"message": message})

    assert response.status_code == 200
    assert response.json == {"reply": "Experiencia documentada."}
    mock_generate.assert_called_once_with(message)


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
