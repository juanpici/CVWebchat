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
