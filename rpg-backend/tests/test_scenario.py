import pytest


class TestScenarioCRUD:
    def test_create_scenario(self, client):
        response = client.post("/scenario/", json={
            "title": "Mysterious Chest",
            "description": "A strange chest appears before you",
            "narrative_text": "You find a weathered chest half-buried in the ground...",
            "triggers": [
                {"type": "location", "zone_id": 1, "x": 10, "y": 10}
            ],
            "outcomes": [
                {
                    "description": "The chest contains gold!",
                    "effect_type": "help",
                    "items_granted": [1],
                    "weight": 3,
                },
                {
                    "description": "The chest was trapped!",
                    "effect_type": "hurt",
                    "health_change": -10,
                    "weight": 1,
                },
            ],
        })
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Mysterious Chest"
        assert len(data["outcomes"]) == 2

    def test_get_scenario(self, client):
        create_resp = client.post("/scenario/", json={
            "title": "Test Scenario",
            "triggers": [],
            "outcomes": [{"description": "Nothing happens", "effect_type": "neutral"}],
        })
        scenario_id = create_resp.json()["id"]

        response = client.get(f"/scenario/{scenario_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Test Scenario"


class TestScenarioTriggering:
    def test_trigger_scenario(self, client):
        # Create character
        char_resp = client.post("/character/", json={
            "name": "Scenario Test",
            "character_class": "warrior",
        })
        char_id = char_resp.json()["id"]

        # Create scenario with single outcome
        scenario_resp = client.post("/scenario/", json={
            "title": "Health Boost",
            "narrative_text": "A healing light envelops you!",
            "outcomes": [
                {
                    "description": "You feel rejuvenated",
                    "effect_type": "help",
                    "health_change": 5,
                }
            ],
        })
        scenario_id = scenario_resp.json()["id"]

        # Trigger
        response = client.post(f"/scenario/{scenario_id}/trigger/{char_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["narrative_text"] == "A healing light envelops you!"
        assert data["effects_applied"]["health_change"]["change"] == 5

    def test_non_repeatable_scenario(self, client):
        # Create character
        char_resp = client.post("/character/", json={
            "name": "NoRepeat Test",
            "character_class": "warrior",
        })
        char_id = char_resp.json()["id"]

        # Create non-repeatable scenario
        scenario_resp = client.post("/scenario/", json={
            "title": "One Time Event",
            "repeatable": False,
            "outcomes": [{"description": "Done", "effect_type": "neutral"}],
        })
        scenario_id = scenario_resp.json()["id"]

        # First trigger should work
        response = client.post(f"/scenario/{scenario_id}/trigger/{char_id}")
        assert response.status_code == 200

        # Second trigger should fail
        response = client.post(f"/scenario/{scenario_id}/trigger/{char_id}")
        assert response.status_code == 422  # Validation error

    def test_scenario_history(self, client):
        # Create character
        char_resp = client.post("/character/", json={
            "name": "History Test",
            "character_class": "mage",
        })
        char_id = char_resp.json()["id"]

        # Create and trigger scenarios
        for i in range(3):
            scenario_resp = client.post("/scenario/", json={
                "title": f"Scenario {i}",
                "repeatable": False,
                "outcomes": [{"description": "Event occurred", "effect_type": "neutral"}],
            })
            client.post(f"/scenario/{scenario_resp.json()['id']}/trigger/{char_id}")

        # Get history
        response = client.get(f"/scenario/history/{char_id}")
        assert response.status_code == 200
        assert len(response.json()) == 3

    def test_scenario_attribute_modifier(self, client):
        # Create character
        char_resp = client.post("/character/", json={
            "name": "Attr Mod Test",
            "character_class": "warrior",
        })
        char_id = char_resp.json()["id"]
        initial_str = char_resp.json()["strength"]

        # Create scenario that modifies strength
        scenario_resp = client.post("/scenario/", json={
            "title": "Strength Blessing",
            "outcomes": [
                {
                    "description": "Your strength increases!",
                    "effect_type": "help",
                    "attribute_modifiers": {"strength": 2},
                }
            ],
        })
        scenario_id = scenario_resp.json()["id"]

        # Trigger
        client.post(f"/scenario/{scenario_id}/trigger/{char_id}")

        # Verify attribute changed
        char_response = client.get(f"/character/{char_id}")
        assert char_response.json()["strength"] == initial_str + 2
