import pytest


class TestQuestCRUD:
    def test_create_quest(self, client):
        response = client.post("/quests/", json={
            "title": "Defeat the Dragon",
            "description": "Slay the dragon terrorizing the village",
            "level_requirement": 10,
            "experience_reward": 1000,
            "gold_reward": 500,
            "objectives": [
                {"description": "Find the dragon's lair", "target_count": 1},
                {"description": "Defeat the dragon", "target_count": 1},
            ],
        })
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Defeat the Dragon"
        assert len(data["objectives"]) == 2
        assert data["experience_reward"] == 1000

    def test_get_quest(self, client):
        create_resp = client.post("/quests/", json={
            "title": "Test Quest",
            "objectives": [{"description": "Do something", "target_count": 1}],
        })
        quest_id = create_resp.json()["id"]

        response = client.get(f"/quests/{quest_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Test Quest"

    def test_list_quests(self, client):
        client.post("/quests/", json={"title": "Quest1", "level_requirement": 1})
        client.post("/quests/", json={"title": "Quest2", "level_requirement": 10})

        response = client.get("/quests/")
        assert response.status_code == 200
        assert len(response.json()) == 2

        # Filter by level
        response = client.get("/quests/?max_level=5")
        assert len(response.json()) == 1


class TestQuestAssignment:
    def test_assign_quest(self, client):
        # Create character
        char_resp = client.post("/character/", json={
            "name": "Quester",
            "character_class": "warrior",
        })
        char_id = char_resp.json()["id"]

        # Create quest
        quest_resp = client.post("/quests/", json={
            "title": "Simple Quest",
            "objectives": [{"description": "Complete task", "target_count": 3}],
        })
        quest_id = quest_resp.json()["id"]

        # Assign
        response = client.post(f"/quests/{quest_id}/assign", json={
            "character_id": char_id,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert len(data["objectives_progress"]) == 1
        assert data["objectives_progress"][0]["current_count"] == 0

    def test_quest_progress(self, client):
        # Create character and quest
        char_resp = client.post("/character/", json={
            "name": "Quester",
            "character_class": "warrior",
        })
        char_id = char_resp.json()["id"]

        quest_resp = client.post("/quests/", json={
            "title": "Kill Quest",
            "objectives": [{"description": "Kill 5 goblins", "target_count": 5}],
        })
        quest_id = quest_resp.json()["id"]
        obj_id = quest_resp.json()["objectives"][0]["id"]

        # Assign
        client.post(f"/quests/{quest_id}/assign", json={"character_id": char_id})

        # Update progress
        response = client.post(f"/quests/{quest_id}/progress?character_id={char_id}", json={
            "objective_id": obj_id,
            "amount": 3,
        })
        assert response.status_code == 200
        assert response.json()["objectives_progress"][0]["current_count"] == 3

        # Add more progress
        response = client.post(f"/quests/{quest_id}/progress?character_id={char_id}", json={
            "objective_id": obj_id,
            "amount": 2,
        })
        assert response.json()["objectives_progress"][0]["current_count"] == 5
        assert response.json()["objectives_progress"][0]["completed"] == True

    def test_complete_quest(self, client):
        # Create character and quest
        char_resp = client.post("/character/", json={
            "name": "Quester",
            "character_class": "warrior",
        })
        char_id = char_resp.json()["id"]

        quest_resp = client.post("/quests/", json={
            "title": "Simple Task",
            "objectives": [{"description": "Do it", "target_count": 1}],
        })
        quest_id = quest_resp.json()["id"]
        obj_id = quest_resp.json()["objectives"][0]["id"]

        # Assign and complete objective
        client.post(f"/quests/{quest_id}/assign", json={"character_id": char_id})
        client.post(f"/quests/{quest_id}/progress?character_id={char_id}", json={
            "objective_id": obj_id, "amount": 1,
        })

        # Complete quest
        response = client.post(f"/quests/{quest_id}/complete?character_id={char_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    def test_abandon_quest(self, client):
        # Create character and quest
        char_resp = client.post("/character/", json={
            "name": "Quester",
            "character_class": "warrior",
        })
        char_id = char_resp.json()["id"]

        quest_resp = client.post("/quests/", json={"title": "Hard Quest"})
        quest_id = quest_resp.json()["id"]

        # Assign then abandon
        client.post(f"/quests/{quest_id}/assign", json={"character_id": char_id})
        response = client.post(f"/quests/{quest_id}/abandon?character_id={char_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "abandoned"
