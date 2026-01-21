"""
Seed script to populate the database with initial game data.

Run with: python -m src.seed
"""

from sqlalchemy.orm import Session
from .database import SessionLocal, engine, Base

# Import ALL models to ensure relationships are registered (same as main.py)
from .character.models import Character, CharacterSkill
from .inventory.models import Item, InventoryItem
from .location.models import Zone, GridCell, Exit
from .quest.models import Quest, QuestObjective, QuestAssignment
from .event.models import GameEvent
from .scenario.models import Scenario, ScenarioHistory
from .combat.models import CombatSession, Combatant, CombatAction

from .core.enums import ItemType


def seed_zones(db: Session) -> dict[str, Zone]:
    """Create initial game zones."""
    zones = {}

    # Check if zones already exist
    existing = db.query(Zone).first()
    if existing:
        print("Zones already seeded, skipping...")
        # Return existing zones by name
        for zone in db.query(Zone).all():
            zones[zone.name] = zone
        return zones

    zone_data = [
        {
            "name": "The Stormhaven Tavern",
            "description": "A cozy tavern with wooden beams and a roaring fireplace. The smell of ale and roasted meat fills the air.",
            "entry_description": "You push open the heavy oak door. Warmth and the sound of clinking mugs wash over you. A grizzled barkeep polishes mugs behind the counter, eyeing newcomers with a practiced gaze.",
        },
        {
            "name": "Stormhaven Market",
            "description": "A bustling marketplace at the heart of the city. Colorful stalls line the cobblestone square.",
            "entry_description": "The market square bustles with activity. Merchants call out their wares while townfolk jostle between colorful stalls. The smell of fresh bread mingles with exotic spices.",
        },
        {
            "name": "Dungeon Entrance",
            "description": "A dark cave mouth at the edge of town, partially hidden by overgrown vines.",
            "entry_description": "Cold air spills from the darkness ahead. Ancient stone steps descend into shadow. You hear distant dripping and something else... a faint skittering.",
        },
        {
            "name": "Castle Gates",
            "description": "The imposing gates of Stormhaven Castle loom overhead, flanked by tall watchtowers.",
            "entry_description": "Two guards in gleaming plate armor stand watch before the massive iron-bound gates. Banners bearing the royal crest flutter in the wind above.",
        },
        {
            "name": "Dungeon Level 1",
            "description": "The first level of the ancient dungeon. Damp stone walls are lined with rusted sconces.",
            "entry_description": "Torchlight flickers on damp stone walls. The air is thick with dust and decay. Something skitters in the shadows ahead, and you catch the glint of bones scattered across the floor.",
        },
    ]

    for data in zone_data:
        zone = Zone(**data)
        db.add(zone)
        zones[data["name"]] = zone

    db.commit()
    for zone in zones.values():
        db.refresh(zone)

    print(f"Created {len(zones)} zones")
    return zones


def seed_exits(db: Session, zones: dict[str, Zone]) -> list[Exit]:
    """Create exits connecting zones."""

    # Check if exits already exist
    existing = db.query(Exit).first()
    if existing:
        print("Exits already seeded, skipping...")
        return db.query(Exit).all()

    tavern = zones["The Stormhaven Tavern"]
    market = zones["Stormhaven Market"]
    dungeon_entrance = zones["Dungeon Entrance"]
    castle = zones["Castle Gates"]
    dungeon_l1 = zones["Dungeon Level 1"]

    exit_data = [
        # From Tavern
        {
            "from_zone_id": tavern.id,
            "to_zone_id": market.id,
            "name": "market gate",
            "description": "A heavy wooden door leads out to the busy market square.",
        },
        {
            "from_zone_id": tavern.id,
            "to_zone_id": dungeon_entrance.id,
            "name": "back alley",
            "description": "A narrow alley behind the tavern leads toward the old caves at the edge of town.",
        },
        # From Market
        {
            "from_zone_id": market.id,
            "to_zone_id": tavern.id,
            "name": "tavern door",
            "description": "The warm glow of the Stormhaven Tavern beckons through its frosted windows.",
        },
        {
            "from_zone_id": market.id,
            "to_zone_id": castle.id,
            "name": "castle road",
            "description": "A wide cobblestone road winds up the hill toward the castle gates.",
        },
        # From Dungeon Entrance
        {
            "from_zone_id": dungeon_entrance.id,
            "to_zone_id": tavern.id,
            "name": "path to town",
            "description": "A muddy path leads back toward the lights of civilization.",
        },
        {
            "from_zone_id": dungeon_entrance.id,
            "to_zone_id": dungeon_l1.id,
            "name": "dark stairwell",
            "description": "Crumbling stone steps descend into the blackness below.",
        },
        # From Castle
        {
            "from_zone_id": castle.id,
            "to_zone_id": market.id,
            "name": "market road",
            "description": "The road leads back down to the bustling market square.",
        },
        # From Dungeon Level 1
        {
            "from_zone_id": dungeon_l1.id,
            "to_zone_id": dungeon_entrance.id,
            "name": "stairs up",
            "description": "The stairwell leads back up toward daylight.",
        },
    ]

    exits = []
    for data in exit_data:
        exit_obj = Exit(**data)
        db.add(exit_obj)
        exits.append(exit_obj)

    db.commit()
    print(f"Created {len(exits)} exits")
    return exits


def seed_items(db: Session) -> dict[str, Item]:
    """Create initial game items."""
    items = {}

    # Check if items already exist
    existing = db.query(Item).filter(Item.name == "Health Potion").first()
    if existing:
        print("Items already seeded, skipping...")
        for item in db.query(Item).all():
            items[item.name] = item
        return items

    item_data = [
        {
            "name": "Health Potion",
            "description": "A red bubbling liquid that restores health when consumed.",
            "item_type": ItemType.CONSUMABLE,
            "value": 50,
            "stackable": True,
            "max_stack": 10,
            "properties": {"heal_amount": 20},
        },
        {
            "name": "Rusty Sword",
            "description": "An old sword with a pitted blade. Still sharp enough to cut.",
            "item_type": ItemType.WEAPON,
            "value": 25,
            "properties": {"damage_dice": "1d6", "damage_type": "slashing"},
        },
        {
            "name": "Leather Armor",
            "description": "Simple but sturdy leather armor offering basic protection.",
            "item_type": ItemType.ARMOR,
            "value": 40,
            "properties": {"armor_bonus": 2, "slot": "chest"},
        },
        {
            "name": "Dungeon Key",
            "description": "An ancient iron key covered in strange runes.",
            "item_type": ItemType.MISC,
            "value": 0,
        },
    ]

    for data in item_data:
        item = Item(**data)
        db.add(item)
        items[data["name"]] = item

    db.commit()
    for item in items.values():
        db.refresh(item)

    print(f"Created {len(items)} items")
    return items


def seed_quests(db: Session, zones: dict[str, Zone], items: dict[str, Item]) -> list[Quest]:
    """Create initial quests (migrated from story_beats.yaml)."""

    # Check if quests already exist
    existing = db.query(Quest).first()
    if existing:
        print("Quests already seeded, skipping...")
        return db.query(Quest).all()

    market = zones["Stormhaven Market"]
    dungeon_entrance = zones["Dungeon Entrance"]

    quests = []

    # Quest 1: Rumors in the Tavern (from story_beats.yaml: tavern_rumor)
    quest1 = Quest(
        title="Rumors in the Stormhaven Tavern",
        description="The barkeep hints at missing caravans and strange noises from the north road. Investigate the rumors to uncover what's happening.",
        experience_reward=50,
        gold_reward=0,
        item_rewards=[],
        prerequisites=[],
    )
    db.add(quest1)
    db.flush()

    obj1a = QuestObjective(
        quest_id=quest1.id,
        description="Ask the barkeep about the missing caravans.",
        target_count=1,
        order=0,
        objective_type="talk_to",
        target_identifier="barkeep",
    )
    obj1b = QuestObjective(
        quest_id=quest1.id,
        description="Head to the market to gather more rumors.",
        target_count=1,
        order=1,
        objective_type="reach_location",
        target_identifier=str(market.id),
    )
    db.add(obj1a)
    db.add(obj1b)
    quests.append(quest1)

    # Quest 2: Stolen Goods (from story_beats.yaml: market_leads)
    quest2 = Quest(
        title="Stolen Goods in the Market",
        description="Merchants describe thefts and point toward the dungeon entrance. Follow the trail to discover who's behind the crimes.",
        experience_reward=75,
        gold_reward=0,
        item_rewards=[],
        prerequisites=[quest1.id],  # Requires tavern_rumor
    )
    db.add(quest2)
    db.flush()

    obj2a = QuestObjective(
        quest_id=quest2.id,
        description="Speak with any merchant about the thefts.",
        target_count=1,
        order=0,
        objective_type="talk_to",
        target_identifier="merchant",
    )
    obj2b = QuestObjective(
        quest_id=quest2.id,
        description="Follow the trail toward the dungeon entrance.",
        target_count=1,
        order=1,
        objective_type="reach_location",
        target_identifier=str(dungeon_entrance.id),
    )
    db.add(obj2a)
    db.add(obj2b)
    quests.append(quest2)

    # Quest 3: Dungeon Omens (from story_beats.yaml: dungeon_omens)
    quest3 = Quest(
        title="Ominous Echoes",
        description="Strange sounds echo from the dungeon. Steel yourself and clear the first threat to discover what lurks below.",
        experience_reward=100,
        gold_reward=40,
        item_rewards=[],
        prerequisites=[quest2.id],  # Requires market_leads
    )
    db.add(quest3)
    db.flush()

    obj3a = QuestObjective(
        quest_id=quest3.id,
        description="Win a combat encounter at the dungeon entrance.",
        target_count=1,
        order=0,
        objective_type="win_combat",
        target_identifier="dungeon",  # Any combat in dungeon areas
    )
    db.add(obj3a)
    quests.append(quest3)

    db.commit()
    print(f"Created {len(quests)} quests")
    return quests


def seed_scenarios(db: Session, zones: dict[str, Zone], quests: list[Quest]) -> list[Scenario]:
    """Create scenarios for narrative triggers (migrated from story_beats.yaml cues)."""

    # Check if scenarios already exist
    existing = db.query(Scenario).first()
    if existing:
        print("Scenarios already seeded, skipping...")
        return db.query(Scenario).all()

    tavern = zones["The Stormhaven Tavern"]
    market = zones["Stormhaven Market"]
    dungeon_entrance = zones["Dungeon Entrance"]

    # Get quest IDs
    quest_ids = {q.title: q.id for q in quests}

    scenarios = []

    # Scenario 1: Tavern entry - grants first quest
    scenario1 = Scenario(
        title="Whispers in the Tavern",
        description="Upon entering the tavern, you notice the patrons seem uneasy.",
        narrative_text="The barkeep leans in, voice low. 'Caravans are vanishing on the road north. Folks whisper about chanting in the old tunnels. If you're looking for work, start at the market—someone there is paying for answers.'",
        triggers=[
            {"type": "location", "zone_id": tavern.id}
        ],
        outcomes=[
            {
                "description": "You learn about the missing caravans and a possible quest.",
                "weight": 1,
                "trigger_quest_id": quest_ids.get("Rumors in the Stormhaven Tavern"),
            }
        ],
        repeatable=False,
    )
    db.add(scenario1)
    scenarios.append(scenario1)

    # Scenario 2: Market entry - grants second quest if first is done
    scenario2 = Scenario(
        title="Nervous Merchants",
        description="The market buzzes with nervous chatter about recent thefts.",
        narrative_text="A merchant pulls you aside, muttering about thieves slipping into the old dungeon. 'If you head that way, keep your eyes open. Something down there wants more than coin.'",
        triggers=[
            {"type": "location", "zone_id": market.id},
            {"type": "quest", "quest_id": quest_ids.get("Rumors in the Stormhaven Tavern"), "quest_status": "completed"},
        ],
        outcomes=[
            {
                "description": "The merchant's warning echoes in your mind.",
                "weight": 1,
                "trigger_quest_id": quest_ids.get("Stolen Goods in the Market"),
            }
        ],
        repeatable=False,
    )
    db.add(scenario2)
    scenarios.append(scenario2)

    # Scenario 3: Dungeon entrance - grants third quest
    scenario3 = Scenario(
        title="Cold Dread",
        description="As you approach the dungeon entrance, a chill runs down your spine.",
        narrative_text="Cold air spills from the stairwell. You catch the metallic scrape of something moving below, and the faint echo of chanting. Whatever is down there is gathering strength.",
        triggers=[
            {"type": "location", "zone_id": dungeon_entrance.id},
            {"type": "quest", "quest_id": quest_ids.get("Stolen Goods in the Market"), "quest_status": "completed"},
        ],
        outcomes=[
            {
                "description": "You steel yourself for what lies ahead.",
                "weight": 1,
                "trigger_quest_id": quest_ids.get("Ominous Echoes"),
            }
        ],
        repeatable=False,
    )
    db.add(scenario3)
    scenarios.append(scenario3)

    # Scenario 4: Low health - can trigger anywhere
    scenario4 = Scenario(
        title="Second Wind",
        description="When critically wounded, you find unexpected reserves of strength.",
        narrative_text="Your vision blurs as pain washes over you. But something deep within refuses to give up. You grit your teeth and push through.",
        triggers=[
            {"type": "health_threshold", "threshold": 0.25, "comparison": "below"}
        ],
        outcomes=[
            {
                "description": "You find a second wind, recovering slightly.",
                "weight": 3,
                "health_change": 5,
            },
            {
                "description": "The pain is too much. You stumble.",
                "weight": 1,
                "health_change": -2,
            },
        ],
        repeatable=True,
        cooldown_seconds=300,  # 5 minute cooldown
    )
    db.add(scenario4)
    scenarios.append(scenario4)

    db.commit()
    print(f"Created {len(scenarios)} scenarios")
    return scenarios


def seed_all():
    """Run all seed functions."""
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Starting database seeding...")
        zones = seed_zones(db)
        exits = seed_exits(db, zones)
        items = seed_items(db)
        quests = seed_quests(db, zones, items)
        scenarios = seed_scenarios(db, zones, quests)
        print("Database seeding complete!")
    finally:
        db.close()


def reseed_all():
    """Clear and reseed the database (useful for development)."""
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Clearing existing data...")
        # Order matters due to foreign keys
        db.query(ScenarioHistory).delete()
        db.query(Scenario).delete()
        db.query(QuestAssignment).delete()
        db.query(QuestObjective).delete()
        db.query(Quest).delete()
        db.query(Exit).delete()
        db.query(GridCell).delete()
        db.query(Zone).delete()
        db.commit()
        print("Data cleared.")

        print("Starting fresh database seeding...")
        zones = seed_zones(db)
        exits = seed_exits(db, zones)
        items = seed_items(db)
        quests = seed_quests(db, zones, items)
        scenarios = seed_scenarios(db, zones, quests)
        print("Database seeding complete!")
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--reseed":
        reseed_all()
    else:
        seed_all()
