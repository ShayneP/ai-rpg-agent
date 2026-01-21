import pytest


class TestCharacterCRUD:
    def test_create_character(self, client):
        response = client.post("/character/", json={
            "name": "Test Hero",
            "character_class": "warrior",
            "character_type": "player",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Hero"
        assert data["character_class"] == "warrior"
        # Warrior should have +2 STR, +1 CON
        assert data["strength"] == 12  # 10 + 2
        assert data["constitution"] == 11  # 10 + 1
        # Warrior should have +10 HP bonus
        assert data["max_hp"] == 20  # 10 + 10

    def test_create_rogue_has_initiative_bonus(self, client):
        response = client.post("/character/", json={
            "name": "Sneaky",
            "character_class": "rogue",
        })
        assert response.status_code == 201
        data = response.json()
        # Rogue should have +2 DEX, +1 CHA
        assert data["dexterity"] == 12
        assert data["charisma"] == 11

    def test_get_character(self, client):
        # Create
        create_resp = client.post("/character/", json={
            "name": "Hero",
            "character_class": "mage",
        })
        char_id = create_resp.json()["id"]

        # Get
        response = client.get(f"/character/{char_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Hero"

    def test_get_nonexistent_character(self, client):
        response = client.get("/character/9999")
        assert response.status_code == 404

    def test_list_characters(self, client):
        # Create multiple characters
        client.post("/character/", json={"name": "Char1", "character_class": "warrior"})
        client.post("/character/", json={"name": "Char2", "character_class": "mage"})

        response = client.get("/character/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_update_character(self, client):
        # Create
        create_resp = client.post("/character/", json={
            "name": "OldName",
            "character_class": "warrior",
        })
        char_id = create_resp.json()["id"]

        # Update
        response = client.put(f"/character/{char_id}", json={"name": "NewName"})
        assert response.status_code == 200
        assert response.json()["name"] == "NewName"

    def test_delete_character(self, client):
        # Create
        create_resp = client.post("/character/", json={
            "name": "ToDelete",
            "character_class": "warrior",
        })
        char_id = create_resp.json()["id"]

        # Delete
        response = client.delete(f"/character/{char_id}")
        assert response.status_code == 204

        # Verify deleted
        get_resp = client.get(f"/character/{char_id}")
        assert get_resp.status_code == 404


class TestCharacterAttributes:
    def test_get_attributes(self, client):
        create_resp = client.post("/character/", json={
            "name": "AttrTest",
            "character_class": "warrior",
        })
        char_id = create_resp.json()["id"]

        response = client.get(f"/character/{char_id}/attributes")
        assert response.status_code == 200
        data = response.json()
        assert "strength" in data
        assert "dexterity" in data

    def test_update_attributes(self, client):
        create_resp = client.post("/character/", json={
            "name": "AttrTest",
            "character_class": "warrior",
        })
        char_id = create_resp.json()["id"]

        response = client.put(f"/character/{char_id}/attributes", json={
            "strength": 18,
            "wisdom": 14,
        })
        assert response.status_code == 200
        assert response.json()["strength"] == 18
        assert response.json()["wisdom"] == 14


class TestCharacterSkills:
    def test_add_skill(self, client):
        create_resp = client.post("/character/", json={
            "name": "SkillTest",
            "character_class": "rogue",
        })
        char_id = create_resp.json()["id"]

        response = client.post(f"/character/{char_id}/skills", json={
            "name": "stealth",
            "level": 3,
            "experience": 100,
        })
        assert response.status_code == 201
        assert response.json()["name"] == "stealth"
        assert response.json()["level"] == 3

    def test_get_skills(self, client):
        create_resp = client.post("/character/", json={
            "name": "SkillTest",
            "character_class": "rogue",
        })
        char_id = create_resp.json()["id"]

        client.post(f"/character/{char_id}/skills", json={"name": "stealth"})
        client.post(f"/character/{char_id}/skills", json={"name": "lockpicking"})

        response = client.get(f"/character/{char_id}/skills")
        assert response.status_code == 200
        assert len(response.json()) == 2


class TestCharacterHealth:
    def test_get_health(self, client):
        create_resp = client.post("/character/", json={
            "name": "HealthTest",
            "character_class": "warrior",
        })
        char_id = create_resp.json()["id"]

        response = client.get(f"/character/{char_id}/health")
        assert response.status_code == 200
        data = response.json()
        assert "current_hp" in data
        assert "max_hp" in data

    def test_update_health(self, client):
        create_resp = client.post("/character/", json={
            "name": "HealthTest",
            "character_class": "warrior",
        })
        char_id = create_resp.json()["id"]

        response = client.put(f"/character/{char_id}/health", json={
            "current_hp": 5,
        })
        assert response.status_code == 200
        assert response.json()["current_hp"] == 5


class TestCharacterLocation:
    def test_update_location(self, client):
        create_resp = client.post("/character/", json={
            "name": "LocTest",
            "character_class": "ranger",
        })
        char_id = create_resp.json()["id"]

        response = client.put(f"/character/{char_id}/location", json={
            "x": 10,
            "y": 20,
        })
        assert response.status_code == 200
        assert response.json()["x"] == 10
        assert response.json()["y"] == 20
