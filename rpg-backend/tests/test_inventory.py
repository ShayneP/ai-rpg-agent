import pytest


class TestItemCRUD:
    def test_create_item(self, client):
        response = client.post("/items/", json={
            "name": "Iron Sword",
            "item_type": "weapon",
            "rarity": "common",
            "weight": 5.0,
            "value": 50,
            "properties": {"damage_dice": "1d8", "damage_type": "slashing"},
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Iron Sword"
        assert data["item_type"] == "weapon"
        assert data["properties"]["damage_dice"] == "1d8"

    def test_get_item(self, client):
        create_resp = client.post("/items/", json={
            "name": "Health Potion",
            "item_type": "consumable",
            "stackable": True,
            "max_stack": 10,
        })
        item_id = create_resp.json()["id"]

        response = client.get(f"/items/{item_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Health Potion"
        assert response.json()["stackable"] == True

    def test_list_items_with_filter(self, client):
        client.post("/items/", json={"name": "Sword", "item_type": "weapon"})
        client.post("/items/", json={"name": "Shield", "item_type": "armor"})
        client.post("/items/", json={"name": "Potion", "item_type": "consumable"})

        response = client.get("/items/?item_type=weapon")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Sword"


class TestInventoryManagement:
    def test_add_item_to_inventory(self, client):
        # Create character
        char_resp = client.post("/character/", json={
            "name": "Inventory Test",
            "character_class": "warrior",
        })
        char_id = char_resp.json()["id"]

        # Create item
        item_resp = client.post("/items/", json={
            "name": "Test Item",
            "item_type": "misc",
        })
        item_id = item_resp.json()["id"]

        # Add to inventory
        response = client.post(f"/character/{char_id}/inventory", json={
            "item_id": item_id,
            "quantity": 1,
        })
        assert response.status_code == 201
        assert response.json()["item_id"] == item_id

    def test_get_inventory(self, client):
        # Create character
        char_resp = client.post("/character/", json={
            "name": "Inventory Test",
            "character_class": "warrior",
        })
        char_id = char_resp.json()["id"]

        # Create and add items
        item1 = client.post("/items/", json={"name": "Item1", "item_type": "misc"}).json()
        item2 = client.post("/items/", json={"name": "Item2", "item_type": "misc"}).json()

        client.post(f"/character/{char_id}/inventory", json={"item_id": item1["id"]})
        client.post(f"/character/{char_id}/inventory", json={"item_id": item2["id"]})

        response = client.get(f"/character/{char_id}/inventory")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_stackable_items(self, client):
        # Create character
        char_resp = client.post("/character/", json={
            "name": "Stack Test",
            "character_class": "warrior",
        })
        char_id = char_resp.json()["id"]

        # Create stackable item
        item_resp = client.post("/items/", json={
            "name": "Arrows",
            "item_type": "misc",
            "stackable": True,
            "max_stack": 20,
        })
        item_id = item_resp.json()["id"]

        # Add to inventory twice
        client.post(f"/character/{char_id}/inventory", json={"item_id": item_id, "quantity": 5})
        response = client.post(f"/character/{char_id}/inventory", json={"item_id": item_id, "quantity": 3})

        # Should stack to 8
        assert response.status_code == 201
        assert response.json()["quantity"] == 8

    def test_equip_item(self, client):
        # Create character
        char_resp = client.post("/character/", json={
            "name": "Equip Test",
            "character_class": "warrior",
        })
        char_id = char_resp.json()["id"]

        # Create weapon
        item_resp = client.post("/items/", json={
            "name": "Steel Sword",
            "item_type": "weapon",
        })
        item_id = item_resp.json()["id"]

        # Add to inventory
        inv_resp = client.post(f"/character/{char_id}/inventory", json={"item_id": item_id})
        inv_item_id = inv_resp.json()["id"]

        # Equip
        response = client.post(f"/character/{char_id}/inventory/{inv_item_id}/equip", json={
            "equipment_slot": "main_hand",
        })
        assert response.status_code == 200
        assert response.json()["equipped"] == True
        assert response.json()["equipment_slot"] == "main_hand"

    def test_remove_from_inventory(self, client):
        # Create character
        char_resp = client.post("/character/", json={
            "name": "Remove Test",
            "character_class": "warrior",
        })
        char_id = char_resp.json()["id"]

        # Create and add item
        item_resp = client.post("/items/", json={"name": "Junk", "item_type": "misc"})
        item_id = item_resp.json()["id"]
        inv_resp = client.post(f"/character/{char_id}/inventory", json={"item_id": item_id})
        inv_item_id = inv_resp.json()["id"]

        # Remove
        response = client.delete(f"/character/{char_id}/inventory/{inv_item_id}")
        assert response.status_code == 204

        # Verify removed
        inv_response = client.get(f"/character/{char_id}/inventory")
        assert len(inv_response.json()) == 0


class TestArmorACBonus:
    def test_equip_armor_increases_ac(self, client):
        """Test that equipping armor adds its AC bonus to the character."""
        # Create character
        char_resp = client.post("/character/", json={
            "name": "Armor Test",
            "character_class": "warrior",
        })
        char_id = char_resp.json()["id"]
        initial_ac = char_resp.json()["armor_class"]

        # Create armor with AC bonus
        armor_resp = client.post("/items/", json={
            "name": "Chain Mail",
            "item_type": "armor",
            "properties": {"armor_bonus": 5},
        })
        armor_id = armor_resp.json()["id"]

        # Add to inventory and equip
        inv_resp = client.post(f"/character/{char_id}/inventory", json={"item_id": armor_id})
        inv_item_id = inv_resp.json()["id"]

        client.post(f"/character/{char_id}/inventory/{inv_item_id}/equip", json={
            "equipment_slot": "chest",
        })

        # Check AC increased
        char_after = client.get(f"/character/{char_id}").json()
        assert char_after["armor_class"] == initial_ac + 5

    def test_unequip_armor_decreases_ac(self, client):
        """Test that unequipping armor removes its AC bonus."""
        # Create character
        char_resp = client.post("/character/", json={
            "name": "Unequip Test",
            "character_class": "warrior",
        })
        char_id = char_resp.json()["id"]
        initial_ac = char_resp.json()["armor_class"]

        # Create and equip armor
        armor_resp = client.post("/items/", json={
            "name": "Plate Armor",
            "item_type": "armor",
            "properties": {"armor_bonus": 8},
        })
        armor_id = armor_resp.json()["id"]

        inv_resp = client.post(f"/character/{char_id}/inventory", json={"item_id": armor_id})
        inv_item_id = inv_resp.json()["id"]

        client.post(f"/character/{char_id}/inventory/{inv_item_id}/equip", json={
            "equipment_slot": "chest",
        })

        # Verify AC increased
        char_equipped = client.get(f"/character/{char_id}").json()
        assert char_equipped["armor_class"] == initial_ac + 8

        # Unequip
        client.post(f"/character/{char_id}/inventory/{inv_item_id}/unequip")

        # Verify AC back to original
        char_unequipped = client.get(f"/character/{char_id}").json()
        assert char_unequipped["armor_class"] == initial_ac

    def test_replace_armor_updates_ac(self, client):
        """Test that replacing armor swaps AC bonuses correctly."""
        # Create character
        char_resp = client.post("/character/", json={
            "name": "Replace Test",
            "character_class": "warrior",
        })
        char_id = char_resp.json()["id"]
        initial_ac = char_resp.json()["armor_class"]

        # Create two armors
        armor1_resp = client.post("/items/", json={
            "name": "Leather Armor",
            "item_type": "armor",
            "properties": {"armor_bonus": 2},
        })
        armor1_id = armor1_resp.json()["id"]

        armor2_resp = client.post("/items/", json={
            "name": "Scale Mail",
            "item_type": "armor",
            "properties": {"armor_bonus": 4},
        })
        armor2_id = armor2_resp.json()["id"]

        # Add both to inventory
        inv1_resp = client.post(f"/character/{char_id}/inventory", json={"item_id": armor1_id})
        inv1_item_id = inv1_resp.json()["id"]

        inv2_resp = client.post(f"/character/{char_id}/inventory", json={"item_id": armor2_id})
        inv2_item_id = inv2_resp.json()["id"]

        # Equip first armor
        client.post(f"/character/{char_id}/inventory/{inv1_item_id}/equip", json={
            "equipment_slot": "chest",
        })
        char_with_armor1 = client.get(f"/character/{char_id}").json()
        assert char_with_armor1["armor_class"] == initial_ac + 2

        # Equip second armor in same slot (should replace first)
        client.post(f"/character/{char_id}/inventory/{inv2_item_id}/equip", json={
            "equipment_slot": "chest",
        })
        char_with_armor2 = client.get(f"/character/{char_id}").json()
        assert char_with_armor2["armor_class"] == initial_ac + 4  # Not +6, replaced
