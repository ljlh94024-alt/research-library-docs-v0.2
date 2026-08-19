from research_library.llm import FakeLLMClient, LLMRequest


def test_fake_llm_is_deterministic_and_offline() -> None:
    client = FakeLLMClient(responses={"known": "fixture answer"}, default_response="fallback")
    request = LLMRequest(prompt="known", model="fake-model")
    assert client.complete(request).text == "fixture answer"
    assert client.complete(LLMRequest(prompt="unknown")).text == "fallback"
    assert client.requests == [request, LLMRequest(prompt="unknown")]
