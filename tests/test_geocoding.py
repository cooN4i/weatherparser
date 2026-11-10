import pytest

from app.services.geocoding import CityResult, GeocodingService


def test_city_result_display_name():
    c1 = CityResult(
        id=1,
        name="Ростов-на-Дону",
        latitude=47.22,
        longitude=39.71,
        country="Россия",
        admin1="Ростовская Область",
        timezone="Europe/Moscow",
    )
    assert c1.display_name == "Ростов-на-Дону, Ростовская Область, Россия"

    c2 = CityResult(
        id=2,
        name="Париж",
        latitude=48.85,
        longitude=2.35,
        country="Франция",
        admin1=None,
        timezone="Europe/Paris",
    )
    assert c2.display_name == "Париж, Франция"


@pytest.mark.asyncio
async def test_search_cities_success(monkeypatch):
    mock_api_data = {
        "results": [
            {
                "id": 501175,
                "name": "Ростов-на-Дону",
                "latitude": 47.21997,
                "longitude": 39.70769,
                "country": "Россия",
                "admin1": "Ростовская Область",
                "timezone": "Europe/Moscow",
            }
        ]
    }

    class MockResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return mock_api_data

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr("httpx.AsyncClient", MockClient)

    results = await GeocodingService.search_cities("Ростов")
    assert len(results) == 1
    assert results[0].name == "Ростов-на-Дону"
    assert results[0].timezone == "Europe/Moscow"
