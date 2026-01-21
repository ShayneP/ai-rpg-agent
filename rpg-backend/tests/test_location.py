import pytest


class TestZoneCRUD:
    def test_create_zone(self, client):
        response = client.post("/location/zones", json={
            "name": "Forest Clearing",
            "description": "A peaceful clearing in the woods",
            "width": 20,
            "height": 20,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Forest Clearing"
        assert data["width"] == 20

    def test_get_zone(self, client):
        create_resp = client.post("/location/zones", json={
            "name": "Test Zone",
            "width": 10,
            "height": 10,
        })
        zone_id = create_resp.json()["id"]

        response = client.get(f"/location/zones/{zone_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Test Zone"

    def test_list_zones(self, client):
        client.post("/location/zones", json={"name": "Zone1", "width": 10, "height": 10})
        client.post("/location/zones", json={"name": "Zone2", "width": 20, "height": 20})

        response = client.get("/location/zones")
        assert response.status_code == 200
        assert len(response.json()) == 2


class TestGridCells:
    def test_create_grid_cell(self, client):
        zone_resp = client.post("/location/zones", json={
            "name": "Grid Test",
            "width": 10,
            "height": 10,
        })
        zone_id = zone_resp.json()["id"]

        response = client.post(f"/location/zones/{zone_id}/cells", json={
            "x": 5,
            "y": 5,
            "terrain_type": "water",
            "passable": False,
        })
        assert response.status_code == 201
        assert response.json()["terrain_type"] == "water"
        assert response.json()["passable"] == False

    def test_get_grid_cell(self, client):
        zone_resp = client.post("/location/zones", json={
            "name": "Grid Test",
            "width": 10,
            "height": 10,
        })
        zone_id = zone_resp.json()["id"]

        client.post(f"/location/zones/{zone_id}/cells", json={
            "x": 3,
            "y": 4,
            "terrain_type": "stone",
        })

        response = client.get(f"/location/zones/{zone_id}/cells/3/4")
        assert response.status_code == 200
        assert response.json()["terrain_type"] == "stone"


class TestSpatialQueries:
    def test_get_characters_at_location(self, client):
        # Create zone
        zone_resp = client.post("/location/zones", json={
            "name": "Spatial Test",
            "width": 100,
            "height": 100,
        })
        zone_id = zone_resp.json()["id"]

        # Create characters at different positions
        char1 = client.post("/character/", json={
            "name": "Char1",
            "character_class": "warrior",
        }).json()
        char2 = client.post("/character/", json={
            "name": "Char2",
            "character_class": "mage",
        }).json()

        # Move to locations
        client.put(f"/character/{char1['id']}/location", json={
            "x": 10, "y": 10, "zone_id": zone_id,
        })
        client.put(f"/character/{char2['id']}/location", json={
            "x": 15, "y": 15, "zone_id": zone_id,
        })

        # Query with radius
        response = client.get(f"/location/characters?zone_id={zone_id}&x=10&y=10&radius=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Char1"

        # Query with larger radius
        response = client.get(f"/location/characters?zone_id={zone_id}&x=10&y=10&radius=10")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_get_surroundings(self, client):
        # Create zone
        zone_resp = client.post("/location/zones", json={
            "name": "Surround Test",
            "width": 50,
            "height": 50,
        })
        zone_id = zone_resp.json()["id"]

        # Create a cell
        client.post(f"/location/zones/{zone_id}/cells", json={
            "x": 25, "y": 25, "terrain_type": "grass",
        })

        # Get surroundings
        response = client.post("/location/surroundings", json={
            "zone_id": zone_id,
            "x": 25,
            "y": 25,
            "radius": 1,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["center_x"] == 25
        assert data["center_y"] == 25
        assert "cells" in data
        assert "characters" in data
        assert "items" in data


class TestExitCRUD:
    def test_create_exit(self, client):
        """Test creating an exit between two zones."""
        # Create two zones
        zone1 = client.post("/location/zones", json={
            "name": "Tavern",
            "description": "A cozy tavern",
            "entry_description": "The smell of ale fills the air.",
        }).json()
        zone2 = client.post("/location/zones", json={
            "name": "Market",
            "description": "A bustling market",
            "entry_description": "Merchants hawk their wares.",
        }).json()

        # Create exit from tavern to market
        response = client.post("/location/exits", json={
            "from_zone_id": zone1["id"],
            "to_zone_id": zone2["id"],
            "name": "market gate",
            "description": "A wooden door leads to the market.",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "market gate"
        assert data["from_zone_id"] == zone1["id"]
        assert data["to_zone_id"] == zone2["id"]
        assert data["locked"] == False
        assert data["hidden"] == False

    def test_get_exit(self, client):
        """Test getting an exit by ID."""
        zone1 = client.post("/location/zones", json={"name": "Zone1"}).json()
        zone2 = client.post("/location/zones", json={"name": "Zone2"}).json()

        create_resp = client.post("/location/exits", json={
            "from_zone_id": zone1["id"],
            "to_zone_id": zone2["id"],
            "name": "door",
        })
        exit_id = create_resp.json()["id"]

        response = client.get(f"/location/exits/{exit_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "door"

    def test_update_exit(self, client):
        """Test updating an exit."""
        zone1 = client.post("/location/zones", json={"name": "Zone1"}).json()
        zone2 = client.post("/location/zones", json={"name": "Zone2"}).json()

        create_resp = client.post("/location/exits", json={
            "from_zone_id": zone1["id"],
            "to_zone_id": zone2["id"],
            "name": "old door",
        })
        exit_id = create_resp.json()["id"]

        response = client.put(f"/location/exits/{exit_id}", json={
            "name": "new door",
            "locked": True,
        })
        assert response.status_code == 200
        assert response.json()["name"] == "new door"
        assert response.json()["locked"] == True

    def test_delete_exit(self, client):
        """Test deleting an exit."""
        zone1 = client.post("/location/zones", json={"name": "Zone1"}).json()
        zone2 = client.post("/location/zones", json={"name": "Zone2"}).json()

        create_resp = client.post("/location/exits", json={
            "from_zone_id": zone1["id"],
            "to_zone_id": zone2["id"],
            "name": "door",
        })
        exit_id = create_resp.json()["id"]

        response = client.delete(f"/location/exits/{exit_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_resp = client.get(f"/location/exits/{exit_id}")
        assert get_resp.status_code == 404

    def test_get_zone_exits(self, client):
        """Test getting all exits from a zone."""
        zone1 = client.post("/location/zones", json={"name": "Central"}).json()
        zone2 = client.post("/location/zones", json={
            "name": "North",
            "entry_description": "Cold winds blow.",
        }).json()
        zone3 = client.post("/location/zones", json={
            "name": "South",
            "entry_description": "Warm sunshine.",
        }).json()

        # Create two exits from zone1
        client.post("/location/exits", json={
            "from_zone_id": zone1["id"],
            "to_zone_id": zone2["id"],
            "name": "north gate",
        })
        client.post("/location/exits", json={
            "from_zone_id": zone1["id"],
            "to_zone_id": zone3["id"],
            "name": "south gate",
        })

        response = client.get(f"/location/zones/{zone1['id']}/exits")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # Check that destination info is included
        names = {e["name"] for e in data}
        assert "north gate" in names
        assert "south gate" in names
        # Check destination zone info
        for exit in data:
            assert "to_zone_name" in exit
            assert "to_zone_entry_description" in exit

    def test_hidden_exits_excluded_by_default(self, client):
        """Test that hidden exits are not returned unless requested."""
        zone1 = client.post("/location/zones", json={"name": "Room"}).json()
        zone2 = client.post("/location/zones", json={"name": "Secret Room"}).json()

        client.post("/location/exits", json={
            "from_zone_id": zone1["id"],
            "to_zone_id": zone2["id"],
            "name": "hidden door",
            "hidden": True,
        })

        # Without include_hidden
        response = client.get(f"/location/zones/{zone1['id']}/exits")
        assert len(response.json()) == 0

        # With include_hidden
        response = client.get(f"/location/zones/{zone1['id']}/exits?include_hidden=true")
        assert len(response.json()) == 1


class TestNavigation:
    def test_travel_through_exit(self, client):
        """Test traveling through an exit updates character location."""
        # Create zones
        tavern = client.post("/location/zones", json={
            "name": "Tavern",
            "entry_description": "You enter the tavern.",
        }).json()
        market = client.post("/location/zones", json={
            "name": "Market",
            "entry_description": "Merchants bustle around you.",
        }).json()

        # Create exit
        exit_resp = client.post("/location/exits", json={
            "from_zone_id": tavern["id"],
            "to_zone_id": market["id"],
            "name": "market door",
        })
        exit_id = exit_resp.json()["id"]

        # Create character in tavern
        char = client.post("/character/", json={
            "name": "Traveler",
            "character_class": "warrior",
        }).json()
        client.put(f"/character/{char['id']}/location", json={
            "zone_id": tavern["id"],
            "x": 0,
            "y": 0,
        })

        # Travel through exit
        response = client.post(f"/location/exits/{exit_id}/travel", json={
            "character_id": char["id"],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "Merchants bustle around you" in data["message"]
        assert data["new_zone"]["id"] == market["id"]

        # Verify character is now in market
        char_resp = client.get(f"/character/{char['id']}")
        assert char_resp.json()["zone_id"] == market["id"]

    def test_travel_returns_available_exits(self, client):
        """Test that travel returns exits from the new zone."""
        zone1 = client.post("/location/zones", json={"name": "Zone1"}).json()
        zone2 = client.post("/location/zones", json={"name": "Zone2"}).json()
        zone3 = client.post("/location/zones", json={"name": "Zone3"}).json()

        # Exit from zone1 to zone2
        exit1 = client.post("/location/exits", json={
            "from_zone_id": zone1["id"],
            "to_zone_id": zone2["id"],
            "name": "forward",
        }).json()

        # Exit from zone2 to zone3
        client.post("/location/exits", json={
            "from_zone_id": zone2["id"],
            "to_zone_id": zone3["id"],
            "name": "continue",
        })

        # Exit back from zone2 to zone1
        client.post("/location/exits", json={
            "from_zone_id": zone2["id"],
            "to_zone_id": zone1["id"],
            "name": "back",
        })

        # Create character and move to zone1
        char = client.post("/character/", json={
            "name": "Test",
            "character_class": "rogue",
        }).json()
        client.put(f"/character/{char['id']}/location", json={
            "zone_id": zone1["id"],
            "x": 0,
            "y": 0,
        })

        # Travel to zone2
        response = client.post(f"/location/exits/{exit1['id']}/travel", json={
            "character_id": char["id"],
        })
        data = response.json()
        assert data["success"] == True
        assert len(data["exits"]) == 2  # "continue" and "back"

    def test_cannot_travel_through_locked_exit(self, client):
        """Test that locked exits block travel."""
        zone1 = client.post("/location/zones", json={"name": "Zone1"}).json()
        zone2 = client.post("/location/zones", json={"name": "Zone2"}).json()

        exit_resp = client.post("/location/exits", json={
            "from_zone_id": zone1["id"],
            "to_zone_id": zone2["id"],
            "name": "locked door",
            "locked": True,
        })
        exit_id = exit_resp.json()["id"]

        char = client.post("/character/", json={
            "name": "Blocked",
            "character_class": "warrior",
        }).json()
        client.put(f"/character/{char['id']}/location", json={
            "zone_id": zone1["id"],
            "x": 0,
            "y": 0,
        })

        response = client.post(f"/location/exits/{exit_id}/travel", json={
            "character_id": char["id"],
        })
        data = response.json()
        assert data["success"] == False
        assert "locked" in data["message"].lower()

    def test_cannot_travel_from_wrong_zone(self, client):
        """Test that character must be in the exit's from_zone."""
        zone1 = client.post("/location/zones", json={"name": "Zone1"}).json()
        zone2 = client.post("/location/zones", json={"name": "Zone2"}).json()
        zone3 = client.post("/location/zones", json={"name": "Zone3"}).json()

        # Exit from zone1 to zone2
        exit_resp = client.post("/location/exits", json={
            "from_zone_id": zone1["id"],
            "to_zone_id": zone2["id"],
            "name": "door",
        })
        exit_id = exit_resp.json()["id"]

        # Character is in zone3, not zone1
        char = client.post("/character/", json={
            "name": "Lost",
            "character_class": "mage",
        }).json()
        client.put(f"/character/{char['id']}/location", json={
            "zone_id": zone3["id"],
            "x": 0,
            "y": 0,
        })

        response = client.post(f"/location/exits/{exit_id}/travel", json={
            "character_id": char["id"],
        })
        data = response.json()
        assert data["success"] == False

    def test_unlock_exit_without_key(self, client):
        """Test unlocking an exit that doesn't require a key."""
        zone1 = client.post("/location/zones", json={"name": "Zone1"}).json()
        zone2 = client.post("/location/zones", json={"name": "Zone2"}).json()

        exit_resp = client.post("/location/exits", json={
            "from_zone_id": zone1["id"],
            "to_zone_id": zone2["id"],
            "name": "door",
            "locked": True,
        })
        exit_id = exit_resp.json()["id"]

        char = client.post("/character/", json={
            "name": "Unlocker",
            "character_class": "rogue",
        }).json()

        response = client.post(f"/location/exits/{exit_id}/unlock", json={
            "character_id": char["id"],
        })
        data = response.json()
        assert data["success"] == True
        assert "unlock" in data["message"].lower()

        # Verify exit is now unlocked
        exit_check = client.get(f"/location/exits/{exit_id}")
        assert exit_check.json()["locked"] == False

    def test_unlock_exit_requires_key(self, client):
        """Test unlocking an exit that requires a specific key item."""
        zone1 = client.post("/location/zones", json={"name": "Zone1"}).json()
        zone2 = client.post("/location/zones", json={"name": "Zone2"}).json()

        # Create a key item (endpoint is /items/, item_type must be valid enum)
        key_resp = client.post("/items/", json={
            "name": "Rusty Key",
            "description": "An old rusty key",
            "item_type": "misc",  # "key" isn't a valid item_type, use misc
        })
        key_id = key_resp.json()["id"]

        # Create locked exit requiring the key
        exit_resp = client.post("/location/exits", json={
            "from_zone_id": zone1["id"],
            "to_zone_id": zone2["id"],
            "name": "locked chest",
            "locked": True,
            "key_item_id": key_id,
        })
        exit_id = exit_resp.json()["id"]

        # Create character without the key
        char = client.post("/character/", json={
            "name": "NoKey",
            "character_class": "warrior",
        }).json()

        # Try to unlock without key
        response = client.post(f"/location/exits/{exit_id}/unlock", json={
            "character_id": char["id"],
        })
        data = response.json()
        assert data["success"] == False
        assert "Rusty Key" in data["message"]

        # Give character the key (endpoint is /character/{id}/inventory)
        client.post(f"/character/{char['id']}/inventory", json={
            "item_id": key_id,
            "quantity": 1,
        })

        # Now unlock should work
        response = client.post(f"/location/exits/{exit_id}/unlock", json={
            "character_id": char["id"],
        })
        data = response.json()
        assert data["success"] == True
