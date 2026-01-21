from typing import Optional


def build_combat_conclusion(combat_result: Optional[dict], location_slug: str) -> str:
    """
    Build a narrative string for combat conclusion based on combat_result payload.
    """
    location = location_slug.replace("_", " ")

    if not combat_result:
        return f"You catch your breath, safe for now in the {location}."

    defeated_names = [name for name, _ in combat_result.get("defeated_enemies", [])]
    if len(defeated_names) == 1:
        victory_message = f"The {defeated_names[0]} lies defeated before you."
    else:
        victory_message = "Your enemies lie defeated."

    xp_gained = combat_result.get("xp_gained", 0)
    if xp_gained > 0:
        victory_message += f" You gained {xp_gained} experience"
        if combat_result.get("level_up"):
            victory_message += f" and feel your power growing - {combat_result['level_up']}"
        else:
            victory_message += " from the encounter"
        victory_message += "."

    loot = combat_result.get("loot", [])
    gold_gained = combat_result.get("gold_gained", 0)
    if loot or gold_gained > 0:
        victory_message += " Among their belongings, you find"
        items_found = []
        if gold_gained > 0:
            items_found.append(f"{gold_gained} gold pieces")
        items_found.extend(loot)

        if items_found:
            if len(items_found) == 1:
                victory_message += f" {items_found[0]}."
            elif len(items_found) == 2:
                victory_message += f" {items_found[0]} and {items_found[1]}."
            else:
                victory_message += f" {', '.join(items_found[:-1])}, and {items_found[-1]}."
        else:
            victory_message += " nothing of value."
    else:
        victory_message += " They carried nothing of value."

    victory_message += f" The {location} grows quiet once more."
    return victory_message
