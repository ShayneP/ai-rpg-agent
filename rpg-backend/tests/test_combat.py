import pytest


class TestCombatInitialization:
    def test_start_combat(self, client):
        # Create characters
        char1 = client.post("/character/", json={
            "name": "Hero",
            "character_class": "warrior",
            "character_type": "player",
        }).json()
        char2 = client.post("/character/", json={
            "name": "Goblin",
            "character_class": "rogue",
            "character_type": "npc",
        }).json()

        # Start combat
        response = client.post("/combat/start", json={
            "participants": [
                {"character_id": char1["id"], "team_id": 1},
                {"character_id": char2["id"], "team_id": 2},
            ],
        })
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "in_progress"
        assert len(data["combatants"]) == 2
        assert len(data["turn_order"]) == 2

    def test_combat_state(self, client):
        # Create characters
        char1 = client.post("/character/", json={
            "name": "Fighter",
            "character_class": "warrior",
            "character_type": "player",
        }).json()
        char2 = client.post("/character/", json={
            "name": "Enemy",
            "character_class": "warrior",
            "character_type": "npc",
        }).json()

        # Start combat
        start_resp = client.post("/combat/start", json={
            "participants": [
                {"character_id": char1["id"], "team_id": 1},
                {"character_id": char2["id"], "team_id": 2},
            ],
        })
        session_id = start_resp.json()["id"]

        # Get state
        response = client.get(f"/combat/{session_id}")
        assert response.status_code == 200
        assert "combatants" in response.json()
        assert "current_combatant" in response.json()


class TestCombatFlow:
    def test_process_npc_turns(self, client):
        # Create NPC-only combat to test auto-processing
        npc1 = client.post("/character/", json={
            "name": "NPC1",
            "character_class": "warrior",
            "character_type": "npc",
        }).json()
        npc2 = client.post("/character/", json={
            "name": "NPC2",
            "character_class": "warrior",
            "character_type": "npc",
        }).json()

        # Start combat
        start_resp = client.post("/combat/start", json={
            "participants": [
                {"character_id": npc1["id"], "team_id": 1},
                {"character_id": npc2["id"], "team_id": 2},
            ],
        })
        session_id = start_resp.json()["id"]

        # Process turns - should complete since all NPCs
        response = client.post(f"/combat/{session_id}/process")
        assert response.status_code == 200
        data = response.json()
        # NPCs will fight until one team wins
        assert data["combat_ended"] == True or len(data["actions_taken"]) > 0

    def test_player_action(self, client):
        # Create player and NPC
        player = client.post("/character/", json={
            "name": "Player",
            "character_class": "warrior",
            "character_type": "player",
            "dexterity": 20,  # High DEX for likely first turn
        }).json()
        npc = client.post("/character/", json={
            "name": "Enemy",
            "character_class": "warrior",
            "character_type": "npc",
            "dexterity": 1,  # Low DEX
        }).json()

        # Start combat
        start_resp = client.post("/combat/start", json={
            "participants": [
                {"character_id": player["id"], "team_id": 1},
                {"character_id": npc["id"], "team_id": 2},
            ],
        })
        session_id = start_resp.json()["id"]

        # Process to get to player turn
        process_resp = client.post(f"/combat/{session_id}/process")

        if process_resp.json()["status"] == "awaiting_player":
            # Get the enemy combatant ID
            combatants = process_resp.json()["combatants"]
            enemy_combatant = next(c for c in combatants if c["team_id"] == 2)

            # Submit player action
            response = client.post(f"/combat/{session_id}/act", json={
                "character_id": player["id"],
                "action_type": "attack",
                "target_id": enemy_combatant["id"],
            })
            assert response.status_code == 200
            assert "action" in response.json()

    def test_defend_action(self, client):
        # Create characters with player having high initiative
        player = client.post("/character/", json={
            "name": "Defender",
            "character_class": "warrior",
            "character_type": "player",
            "dexterity": 20,
        }).json()
        npc = client.post("/character/", json={
            "name": "Attacker",
            "character_class": "warrior",
            "character_type": "npc",
            "dexterity": 1,
        }).json()

        # Start combat
        start_resp = client.post("/combat/start", json={
            "participants": [
                {"character_id": player["id"], "team_id": 1},
                {"character_id": npc["id"], "team_id": 2},
            ],
        })
        session_id = start_resp.json()["id"]

        # Process to player turn
        client.post(f"/combat/{session_id}/process")

        # Defend
        response = client.post(f"/combat/{session_id}/act", json={
            "character_id": player["id"],
            "action_type": "defend",
        })
        if response.status_code == 200:
            # Check that AC increased
            state = client.get(f"/combat/{session_id}").json()
            player_combatant = next(
                c for c in state["combatants"]
                if c["character_id"] == player["id"]
            )
            assert "defending" in player_combatant["status_effects"]


class TestCombatResolution:
    def test_finish_combat(self, client):
        # Create two weak NPCs for fast combat
        npc1 = client.post("/character/", json={
            "name": "Weak1",
            "character_class": "mage",
            "character_type": "npc",
        }).json()
        npc2 = client.post("/character/", json={
            "name": "Weak2",
            "character_class": "mage",
            "character_type": "npc",
        }).json()

        # Update their HP to be very low
        client.put(f"/character/{npc1['id']}/health", json={"current_hp": 1, "max_hp": 1})
        client.put(f"/character/{npc2['id']}/health", json={"current_hp": 1, "max_hp": 1})

        # Start combat
        start_resp = client.post("/combat/start", json={
            "participants": [
                {"character_id": npc1["id"], "team_id": 1},
                {"character_id": npc2["id"], "team_id": 2},
            ],
        })
        session_id = start_resp.json()["id"]

        # Process until done
        for _ in range(20):  # Max iterations
            process_resp = client.post(f"/combat/{session_id}/process")
            if process_resp.json()["combat_ended"]:
                break

        # Finish
        response = client.post(f"/combat/{session_id}/finish")
        assert response.status_code == 200
        data = response.json()
        assert data["winner_team_id"] is not None
        assert "total_rounds" in data

    def test_combat_history(self, client):
        # Create NPCs
        npc1 = client.post("/character/", json={
            "name": "Hist1",
            "character_class": "warrior",
            "character_type": "npc",
        }).json()
        npc2 = client.post("/character/", json={
            "name": "Hist2",
            "character_class": "warrior",
            "character_type": "npc",
        }).json()

        # Start combat
        start_resp = client.post("/combat/start", json={
            "participants": [
                {"character_id": npc1["id"], "team_id": 1},
                {"character_id": npc2["id"], "team_id": 2},
            ],
        })
        session_id = start_resp.json()["id"]

        # Process some turns
        client.post(f"/combat/{session_id}/process")

        # Get history
        response = client.get(f"/combat/{session_id}/history")
        assert response.status_code == 200
        assert "actions" in response.json()

    def test_character_hp_syncs_after_combat(self, client):
        """Test that character HP is updated after taking damage in combat."""
        # Create two NPCs with low HP for quick combat
        npc1 = client.post("/character/", json={
            "name": "Attacker",
            "character_class": "warrior",
            "character_type": "npc",
            "strength": 18,  # High strength for damage
        }).json()
        npc2 = client.post("/character/", json={
            "name": "Victim",
            "character_class": "mage",
            "character_type": "npc",
        }).json()

        # Set victim to low HP
        client.put(f"/character/{npc2['id']}/health", json={"current_hp": 5, "max_hp": 5})

        # Verify initial HP
        victim_before = client.get(f"/character/{npc2['id']}").json()
        assert victim_before["current_hp"] == 5

        # Start combat
        start_resp = client.post("/combat/start", json={
            "participants": [
                {"character_id": npc1["id"], "team_id": 1},
                {"character_id": npc2["id"], "team_id": 2},
            ],
        })
        session_id = start_resp.json()["id"]

        # Process until combat ends
        for _ in range(20):
            process_resp = client.post(f"/combat/{session_id}/process")
            if process_resp.json()["combat_ended"]:
                break

        # Finish combat
        client.post(f"/combat/{session_id}/finish")

        # Check that the victim's HP was updated on the character record
        victim_after = client.get(f"/character/{npc2['id']}").json()

        # The victim should have taken damage (HP decreased from 5)
        # If they died, HP should be 0
        assert victim_after["current_hp"] < victim_before["current_hp"] or victim_after["current_hp"] == 0
