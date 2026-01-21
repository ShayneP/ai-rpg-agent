import pytest


class TestEventLogging:
    def test_log_event(self, client):
        response = client.post("/events/", json={
            "event_type": "item_acquired",
            "character_id": 1,
            "item_id": 5,
            "description": "Found a sword in a chest",
            "data": {"source": "treasure_chest"},
        })
        assert response.status_code == 201
        data = response.json()
        assert data["event_type"] == "item_acquired"
        assert data["data"]["source"] == "treasure_chest"

    def test_get_event(self, client):
        create_resp = client.post("/events/", json={
            "event_type": "level_up",
            "character_id": 1,
            "data": {"new_level": 5},
        })
        event_id = create_resp.json()["id"]

        response = client.get(f"/events/{event_id}")
        assert response.status_code == 200
        assert response.json()["event_type"] == "level_up"

    def test_list_events(self, client):
        client.post("/events/", json={"event_type": "combat_start"})
        client.post("/events/", json={"event_type": "combat_end"})
        client.post("/events/", json={"event_type": "item_acquired"})

        response = client.get("/events/")
        assert response.status_code == 200
        assert len(response.json()) == 3

    def test_query_events(self, client):
        # Create character
        char_resp = client.post("/character/", json={
            "name": "Event Test",
            "character_class": "warrior",
        })
        char_id = char_resp.json()["id"]

        # Log events
        client.post("/events/", json={
            "event_type": "item_acquired",
            "character_id": char_id,
        })
        client.post("/events/", json={
            "event_type": "level_up",
            "character_id": char_id,
        })
        client.post("/events/", json={
            "event_type": "item_acquired",
            "character_id": 999,  # Different character
        })

        # Query by character
        response = client.post("/events/query", json={
            "character_id": char_id,
        })
        assert response.status_code == 200
        assert len(response.json()) == 2

        # Query by event type
        response = client.post("/events/query", json={
            "event_type": "item_acquired",
        })
        assert len(response.json()) == 2
