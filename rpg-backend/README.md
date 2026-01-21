# Tabletop RPG Game Loop API

A FastAPI application for managing tabletop RPG game state including characters, inventory, locations, quests, events, scenarios, and turn-based combat.

## Integration with Voice Agent

This API serves as the backend for the **Dungeons and Agents** voice-driven RPG. The architecture:

```
Frontend (Next.js) <--LiveKit RPC--> Voice Agent (Python) <--HTTP--> This API (FastAPI)
```

- **Voice Agent** (`role-playing/`): LiveKit-based voice agent that handles speech-to-text, LLM processing, and text-to-speech
- **This API** (`rpg-backend/`): Stateless game mechanics API - handles combat, inventory, quests, etc.
- **Frontend** (`role-playing/role_playing_frontend/`): Next.js web interface

The voice agent stores only IDs and fetches state from this API as needed. All game mechanics (dice rolls, combat resolution, skill checks) are handled here.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Running the Server](#running-the-server)
- [API Documentation](#api-documentation)
- [Data Models](#data-models)
- [Character System](#character-system)
- [Inventory System](#inventory-system)
- [Location System](#location-system)
- [Quest System](#quest-system)
- [Event System](#event-system)
- [Scenario System](#scenario-system)
- [Combat System](#combat-system)
- [Reference Data](#reference-data)
- [Monster System](#monster-system)
- [Database Migrations](#database-migrations)
- [Testing](#testing)
- [Web Application](#web-application)

## Features

- **Character Management**: Create and manage player characters and NPCs with attributes, skills, health, and location tracking
- **Class System**: Five character classes with unique bonuses (Warrior, Mage, Rogue, Cleric, Ranger)
- **Character Progression**: Experience points, leveling system with XP thresholds, gold currency
- **Spell System**: Spell slots for spellcasters, 16 spells from cantrips to level 3, class-restricted casting
- **Class Abilities**: 14 unique class abilities with cooldowns and per-rest limits
- **Inventory System**: Items with types, rarity, stackable items, equipment slots, weapon damage dice, and armor AC bonuses
- **Consumables**: Healing potions, buff items, damage throwables, and cure items usable in combat
- **Status Effects**: 15 status effects with durations, damage over time, and combat modifiers
- **Location System**: Zone-based grid system with terrain types, effects, and spatial queries
- **Terrain Effects**: Difficult terrain, hazardous terrain with damage, cover bonuses for combat
- **Quest System**: Quest tracking with multiple objectives, progress tracking, and prerequisites
- **Event Logging**: Comprehensive game event logging with filtering and queries
- **Scenario System**: Story events with triggers and weighted random outcomes
- **Combat Engine**: Turn-based combat with initiative, threat-based targeting, spells, abilities, items, ranged combat, death saving throws, and multiple action types
- **Rest System**: Short and long rests for HP, spell slot, and ability recovery
- **Reference Data**: Pre-built databases for weapons (37), armor (13), spells (16), consumables (11), status effects (15), class abilities (14), monsters (24), and loot tables (16)
- **Loot System**: Weighted loot tables attached to monsters, rolled on combat victory
- **Web Application**: Browser-based frontend for interacting with the API

## Installation

### Prerequisites

- Python 3.10+
- pip

### Setup

1. Clone the repository and navigate to the project directory:

```bash
cd tabletop-rpg-api
```

2. Create a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -e ".[dev]"
```

Or using requirements.txt:

```bash
pip install -r requirements.txt
```

## Running the Server

Start the development server:

```bash
uvicorn src.main:app --reload
```

The server will be available at `http://localhost:8000`.

### API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Documentation

### Base URL

All endpoints are relative to `http://localhost:8000`.

### Endpoints Overview

| Module | Prefix | Description |
|--------|--------|-------------|
| Character | `/character` | Character CRUD and sub-resources |
| Items | `/items` | Item definitions CRUD |
| Location | `/location` | Zones, grid cells, spatial queries |
| Quests | `/quests` | Quest management and progress |
| Events | `/events` | Game event logging |
| Scenario | `/scenario` | Story scenarios and triggers |
| Combat | `/combat` | Combat session management |
| Reference | `/reference` | Base weapon data and game reference |

---

## Data Models

### Character

| Field | Type | Description |
|-------|------|-------------|
| id | int | Unique identifier |
| name | string | Character name |
| character_class | enum | warrior, mage, rogue, cleric, ranger |
| character_type | enum | player, npc |
| status | enum | alive, unconscious, dead |
| level | int | Character level (1-20) |
| experience | int | Experience points |
| gold | int | Currency |
| strength | int | STR attribute (1-30) |
| dexterity | int | DEX attribute (1-30) |
| constitution | int | CON attribute (1-30) |
| intelligence | int | INT attribute (1-30) |
| wisdom | int | WIS attribute (1-30) |
| charisma | int | CHA attribute (1-30) |
| current_hp | int | Current hit points |
| max_hp | int | Maximum hit points |
| temporary_hp | int | Temporary hit points |
| armor_class | int | AC for combat |
| spell_slots | JSON | Current spell slots by level (e.g., {"1": 2, "2": 1}) |
| max_spell_slots | JSON | Maximum spell slots by level |
| ability_uses | JSON | Remaining ability uses (e.g., {"second_wind": 1}) |
| death_save_successes | int | Death saving throw successes (0-3) |
| death_save_failures | int | Death saving throw failures (0-3) |
| is_stable | bool | Whether character is stable (after 3 successes) |
| monster_id | string | Monster template ID (for loot tables) |
| x, y | int | Grid position |
| zone_id | int | Current zone |

### Item

| Field | Type | Description |
|-------|------|-------------|
| id | int | Unique identifier |
| name | string | Item name |
| description | string | Item description |
| item_type | enum | weapon, armor, consumable, quest, misc |
| rarity | enum | common, uncommon, rare, epic, legendary |
| weight | float | Item weight |
| value | int | Gold value |
| stackable | bool | Can be stacked |
| max_stack | int | Maximum stack size |
| properties | JSON | Type-specific properties |

### Zone

| Field | Type | Description |
|-------|------|-------------|
| id | int | Unique identifier |
| name | string | Zone name |
| description | string | Zone description |
| width | int | Grid width |
| height | int | Grid height |

### Quest

| Field | Type | Description |
|-------|------|-------------|
| id | int | Unique identifier |
| title | string | Quest title |
| description | string | Quest description |
| level_requirement | int | Minimum level |
| experience_reward | int | XP reward |
| gold_reward | int | Gold reward |
| item_rewards | list[int] | Item IDs as rewards |
| prerequisites | list[int] | Required quest IDs |
| objectives | list | Quest objectives |

---

## Character System

### Character Classes

| Class | Primary Stat | Bonuses |
|-------|--------------|---------|
| Warrior | STR | +2 STR, +1 CON, +10 base HP |
| Mage | INT | +2 INT, +1 WIS |
| Rogue | DEX | +2 DEX, +1 CHA, +2 initiative |
| Cleric | WIS | +2 WIS, +1 CON |
| Ranger | DEX | +1 DEX, +1 WIS, +1 STR |

### Endpoints

#### Create Character
```http
POST /character/
Content-Type: application/json

{
  "name": "Aragorn",
  "character_class": "warrior",
  "character_type": "player"
}
```

#### Get Character
```http
GET /character/{id}
```

#### List Characters
```http
GET /character/?character_type=player&zone_id=1
```

#### Update Character
```http
PUT /character/{id}
Content-Type: application/json

{
  "name": "New Name",
  "level": 5
}
```

#### Delete Character
```http
DELETE /character/{id}
```

#### Attributes
```http
GET /character/{id}/attributes
PUT /character/{id}/attributes
```

#### Skills
```http
GET /character/{id}/skills
POST /character/{id}/skills
PUT /character/{id}/skills/{skill_name}
```

#### Health
```http
GET /character/{id}/health
PUT /character/{id}/health
```

#### Location
```http
GET /character/{id}/location
PUT /character/{id}/location
```

#### Inventory
```http
GET /character/{id}/inventory
POST /character/{id}/inventory
DELETE /character/{id}/inventory/{item_id}
POST /character/{id}/inventory/{item_id}/equip
POST /character/{id}/inventory/{item_id}/unequip
```

#### Experience and Leveling
```http
POST /character/{id}/experience?amount=100   # Award XP (auto-levels if threshold reached)
POST /character/{id}/level-up                # Manual level up if enough XP
GET /character/{id}/xp-status                # Get XP progress to next level
```

#### Gold
```http
POST /character/{id}/gold?amount=50          # Add gold (use negative to remove)
```

#### Spell Slots
```http
GET /character/{id}/spell-slots              # Get current and max spell slots
```

#### Rest and Recovery
```http
POST /character/{id}/rest?rest_type=short    # Short rest: half HP, short-rest abilities
POST /character/{id}/rest?rest_type=long     # Long rest: full HP, all spell slots, all abilities
```

---

## Character Progression

### Experience Thresholds

Characters level up when reaching these XP totals:

| Level | XP Required | Level | XP Required |
|-------|-------------|-------|-------------|
| 1 | 0 | 11 | 85,000 |
| 2 | 300 | 12 | 100,000 |
| 3 | 900 | 13 | 120,000 |
| 4 | 2,700 | 14 | 140,000 |
| 5 | 6,500 | 15 | 165,000 |
| 6 | 14,000 | 16 | 195,000 |
| 7 | 23,000 | 17 | 225,000 |
| 8 | 34,000 | 18 | 265,000 |
| 9 | 48,000 | 19 | 305,000 |
| 10 | 64,000 | 20 | 355,000 |

### Level Up Benefits

When a character levels up:
- HP increases based on class and constitution
- Spellcasters gain additional spell slots
- New class abilities may become available

### Rest Mechanics

| Rest Type | HP Recovery | Spell Slots | Abilities |
|-----------|-------------|-------------|-----------|
| Short | Half max HP | None | Short-rest abilities only |
| Long | Full HP | All slots restored | All abilities restored |

---

## Inventory System

### Item Types

- **weapon**: Damage-dealing items with damage_dice, damage_type, hit_bonus properties
- **armor**: Protective items with armor_bonus property (applied to character AC when equipped)
- **consumable**: Single-use items (potions, scrolls)
- **quest**: Quest-related items
- **misc**: Miscellaneous items

### Rarity Levels

common → uncommon → rare → epic → legendary

### Weapon Properties

When equipped in `main_hand` or `off_hand`, weapons affect combat:

| Property | Type | Description |
|----------|------|-------------|
| damage_dice | string | Dice to roll for damage (e.g., "1d8", "2d6") |
| damage_type | string | Type of damage (slashing, piercing, bludgeoning) |
| hit_bonus | int | Bonus to attack rolls (e.g., +1, +3 for magic weapons) |

**Unarmed attacks** deal `1d4` damage.

### Armor Properties

When armor is equipped, its `armor_bonus` is automatically added to the character's AC. When unequipped, the bonus is removed.

| Property | Type | Description |
|----------|------|-------------|
| armor_bonus | int | AC bonus when equipped (e.g., +2 for leather, +6 for plate) |

### Endpoints

#### Create Weapon
```http
POST /items/
Content-Type: application/json

{
  "name": "Longsword +1",
  "item_type": "weapon",
  "rarity": "uncommon",
  "weight": 3.0,
  "value": 100,
  "properties": {
    "damage_dice": "1d8",
    "damage_type": "slashing",
    "hit_bonus": 1
  }
}
```

#### Create Armor
```http
POST /items/
Content-Type: application/json

{
  "name": "Chain Mail",
  "item_type": "armor",
  "rarity": "common",
  "weight": 55.0,
  "value": 75,
  "properties": {
    "armor_bonus": 6
  }
}
```

#### Create Basic Item
```http
POST /items/
Content-Type: application/json

{
  "name": "Iron Sword",
  "item_type": "weapon",
  "rarity": "common",
  "weight": 5.0,
  "value": 50,
  "properties": {
    "damage_dice": "1d8",
    "damage_type": "slashing"
  }
}
```

#### Add to Inventory
```http
POST /character/{id}/inventory
Content-Type: application/json

{
  "item_id": 1,
  "quantity": 1
}
```

#### Equip Item
```http
POST /character/{id}/inventory/{inventory_item_id}/equip
Content-Type: application/json

{
  "equipment_slot": "main_hand"
}
```

---

## Spell System

Spellcasting classes (Mage, Cleric) have access to spells that consume spell slots. Rangers also have access to some spells at higher levels.

### Spell Slots by Level

Spellcasters gain spell slots as they level up:

| Character Level | 1st | 2nd | 3rd | 4th | 5th |
|-----------------|-----|-----|-----|-----|-----|
| 1 | 2 | - | - | - | - |
| 2 | 3 | - | - | - | - |
| 3 | 4 | 2 | - | - | - |
| 4 | 4 | 3 | - | - | - |
| 5 | 4 | 3 | 2 | - | - |
| 6 | 4 | 3 | 3 | - | - |
| 7 | 4 | 3 | 3 | 1 | - |
| 8 | 4 | 3 | 3 | 2 | - |
| 9 | 4 | 3 | 3 | 3 | 1 |
| 10 | 4 | 3 | 3 | 3 | 2 |

### Available Spells

The system includes 16 spells in `data/spells.json`:

| Spell | Level | Class | Effect |
|-------|-------|-------|--------|
| Fire Bolt | 0 (cantrip) | Mage | 1d10 fire damage |
| Ray of Frost | 0 (cantrip) | Mage | 1d8 cold damage |
| Sacred Flame | 0 (cantrip) | Cleric | 1d8 radiant damage |
| Magic Missile | 1 | Mage | 3d4+3 force (auto-hit) |
| Burning Hands | 1 | Mage | 3d6 fire (area) |
| Cure Wounds | 1 | Cleric | 1d8 healing |
| Healing Word | 1 | Cleric | 1d4 healing |
| Shield of Faith | 1 | Cleric | +2 AC buff |
| Thunderwave | 1 | Mage | 2d8 thunder (area) |
| Scorching Ray | 2 | Mage | 3×2d6 fire |
| Hold Person | 2 | Mage, Cleric | Paralyzed status |
| Prayer of Healing | 2 | Cleric | 2d8 healing (area) |
| Fireball | 3 | Mage | 8d6 fire (area) |
| Lightning Bolt | 3 | Mage | 8d6 lightning |
| Mass Healing Word | 3 | Cleric | 1d4 healing (area) |
| Revivify | 3 | Cleric | Restore to 1 HP |

### Casting Spells in Combat

```http
POST /combat/{id}/act
Content-Type: application/json

{
  "character_id": 1,
  "action_type": "spell",
  "spell_name": "Fireball",
  "target_id": 3
}
```

- Cantrips (level 0) can be cast unlimited times
- Higher level spells consume a spell slot of that level
- Spell slots are restored on long rest
- Class restrictions apply (Mages can't cast Cleric spells and vice versa)

### Reference Endpoints

```http
GET /reference/spells                        # List all spells
GET /reference/spells?level=1               # Filter by spell level
GET /reference/spells?character_class=mage  # Filter by class
GET /reference/spells?healing=true          # Filter healing spells
GET /reference/spells/{spell_name}          # Get specific spell
GET /reference/spells/class/{class_name}    # Get all spells for a class
```

---

## Location System

### Terrain Types

| Terrain | Movement Cost | Passable | Hazardous | Cover Bonus | Effects |
|---------|---------------|----------|-----------|-------------|---------|
| grass | 1 | Yes | No | 0 | - |
| stone | 1 | Yes | No | 0 | - |
| water | 2 | Yes | No | 0 | - |
| forest | 2 | Yes | No | +2 AC | - |
| mountain | - | No | No | +4 AC | - |
| sand | 2 | Yes | No | 0 | - |
| swamp | 3 | Yes | No | 0 | Poisoned |
| lava | 1 | Yes | Yes | 0 | Burning (10 dmg on enter, 5/turn) |
| ice | 2 | Yes | No | 0 | - |
| void | - | No | Yes | 0 | Instant death (9999 dmg) |

### Terrain Effects

Terrain effects are applied when characters move:
- **Movement Cost**: Difficult terrain (cost > 1) consumes more movement
- **Hazardous Terrain**: Deals damage when entered and/or each turn
- **Cover Bonus**: Adds to AC when targeted in combat
- **Status Effects**: Some terrain applies status effects

#### Move Character with Terrain Processing
```http
POST /character/{character_id}/move?x=10&y=10&zone_id=1
```

Response includes:
```json
{
  "character_id": 1,
  "from_x": 5, "from_y": 5,
  "to_x": 10, "to_y": 10,
  "terrain_effect": {"name": "Molten Lava", "damage_on_enter": 10},
  "damage_taken": 10,
  "movement_cost": 1,
  "blocked": false,
  "status_effects_applied": ["burning"]
}
```

If terrain is impassable, the move is blocked:
```json
{
  "blocked": true,
  "block_reason": "Terrain is impassable (Rocky Mountain)"
}
```

### Endpoints

#### Create Zone
```http
POST /location/zones
Content-Type: application/json

{
  "name": "Dark Forest",
  "description": "A mysterious forest",
  "width": 50,
  "height": 50
}
```

#### Create Grid Cell
```http
POST /location/zones/{zone_id}/cells
Content-Type: application/json

{
  "x": 10,
  "y": 10,
  "terrain_type": "forest",
  "passable": true
}
```

#### Query Characters at Location
```http
GET /location/characters?zone_id=1&x=10&y=10&radius=5
```

#### Query Items at Location
```http
GET /location/items?zone_id=1&x=10&y=10&radius=5
```

#### Get Surroundings
```http
POST /location/surroundings
Content-Type: application/json

{
  "zone_id": 1,
  "x": 25,
  "y": 25,
  "radius": 3
}
```

Returns cells, characters, and items within the radius.

---

## Quest System

The quest system provides storage and tracking for quests. Quest progression is **LLM-driven** - the voice agent decides when to progress quests based on player actions, rather than automatic API-side triggers.

### Quest Status

- **available**: Can be accepted
- **active**: Currently in progress
- **completed**: Successfully finished
- **failed**: Failed to complete
- **abandoned**: Given up by player

### Endpoints

#### Create Quest
```http
POST /quests/
Content-Type: application/json

{
  "title": "Defeat the Dragon",
  "description": "Slay the dragon terrorizing the village",
  "level_requirement": 10,
  "experience_reward": 1000,
  "gold_reward": 500,
  "objectives": [
    {"description": "Find the dragon's lair", "target_count": 1},
    {"description": "Defeat the dragon", "target_count": 1}
  ]
}
```

#### Assign Quest to Character
```http
POST /quests/{quest_id}/assign
Content-Type: application/json

{
  "character_id": 1
}
```

#### Update Objective Progress
```http
POST /quests/{quest_id}/progress?character_id=1
Content-Type: application/json

{
  "objective_id": 1,
  "amount": 1
}
```

#### Complete Quest
```http
POST /quests/{quest_id}/complete?character_id=1
```

#### Abandon Quest
```http
POST /quests/{quest_id}/abandon?character_id=1
```

#### Get Character's Quests
```http
GET /quests/character/{character_id}?status=active
```

---

## Event System

### Event Types

| Type | Description |
|------|-------------|
| combat_start | Combat session began |
| combat_end | Combat session ended |
| character_death | Character died |
| item_acquired | Item was obtained |
| item_used | Item was consumed |
| quest_started | Quest was accepted |
| quest_completed | Quest was finished |
| level_up | Character leveled up |
| location_change | Character moved |
| scenario_triggered | Scenario was activated |
| custom | Custom event |

### Endpoints

#### Log Event
```http
POST /events/
Content-Type: application/json

{
  "event_type": "item_acquired",
  "character_id": 1,
  "item_id": 5,
  "description": "Found a sword in a chest",
  "data": {"source": "treasure_chest"}
}
```

#### Query Events
```http
POST /events/query
Content-Type: application/json

{
  "event_type": "combat_start",
  "character_id": 1,
  "limit": 50
}
```

---

## Scenario System

Scenarios are story events that can be triggered under certain conditions and produce outcomes that affect the game state.

### Trigger Types

- **location**: Activates at specific coordinates
- **item**: Activates when character has an item
- **quest**: Activates based on quest status
- **health_threshold**: Activates based on HP percentage

### Outcome Effects

- **health_change**: Modify HP
- **attribute_modifiers**: Change attributes
- **items_granted**: Add items to inventory
- **items_removed**: Remove items from inventory
- **trigger_quest_id**: Start a quest

### Endpoints

#### Create Scenario
```http
POST /scenario/
Content-Type: application/json

{
  "title": "Mysterious Chest",
  "narrative_text": "You find a weathered chest...",
  "triggers": [
    {"type": "location", "zone_id": 1, "x": 10, "y": 10}
  ],
  "outcomes": [
    {
      "description": "The chest contains gold!",
      "effect_type": "help",
      "items_granted": [1, 2],
      "weight": 3
    },
    {
      "description": "The chest was trapped!",
      "effect_type": "hurt",
      "health_change": -10,
      "weight": 1
    }
  ],
  "repeatable": false
}
```

#### Trigger Scenario
```http
POST /scenario/{scenario_id}/trigger/{character_id}
Content-Type: application/json

{
  "outcome_index": null  // null for random weighted selection
}
```

#### Get Character's Scenario History
```http
GET /scenario/history/{character_id}
```

#### Evaluate Scenarios for Character
Check which scenarios are applicable for a character based on their current state.
```http
GET /scenario/evaluate/{character_id}?trigger_type=location&auto_trigger=false
```

Query parameters:
- `trigger_type` (optional): Filter by trigger type (location, item, quest, health_threshold)
- `auto_trigger` (optional): If true, automatically trigger the first applicable scenario

Response:
```json
{
  "character_id": 1,
  "applicable_scenarios": [
    {
      "id": 1,
      "title": "Mysterious Chest",
      "narrative_text": "You find a weathered chest...",
      "triggers": [{"type": "location", "zone_id": 1, "x": 10, "y": 10}]
    }
  ],
  "count": 1,
  "triggered": null  // Present only if auto_trigger=true and a scenario was triggered
}
```

This endpoint evaluates all scenarios in the system and returns those that:
1. Have not been triggered yet (for non-repeatable scenarios)
2. Are not on cooldown (for repeatable scenarios)
3. Have all trigger conditions met by the character's current state

---

## Combat System

The combat engine implements turn-based combat with initiative ordering, threat-based targeting, and multiple action types.

### Combat Flow

```
1. POST /combat/start     → Initialize combat, calculate initiative
2. POST /combat/{id}/process → Process NPC turns until player action needed
3. POST /combat/{id}/act     → Player submits their action
4. Repeat steps 2-3 until one team remains
5. POST /combat/{id}/resolve → Calculate rewards
6. POST /combat/{id}/finish  → End combat, get summary
```

### Combat Status States

```
initializing → in_progress ⟷ awaiting_player → resolving → finished
```

### Initiative System

- **Formula**: d20 + (DEX - 10) / 2
- **Rogues**: +2 bonus to initiative
- **Ties**: Broken randomly

### Initiative Variants

The combat system supports different initiative types, specified when starting combat:

| Type | Description |
|------|-------------|
| `individual` | (Default) Each combatant rolls initiative separately |
| `group` | One roll per team; all team members share the same initiative |
| `side` | Teams alternate turns (all of Team 1 acts, then all of Team 2) |
| `reroll` | Initiative is re-rolled at the start of each round |

**Starting combat with a variant:**
```http
POST /combat/start
{
  "participants": [...],
  "initiative_type": "group"
}
```

**Group Initiative**: Useful for simpler, faster combat. One roll per team determines when that team acts.

**Side Initiative**: Classic "sides take turns" combat. All members of the winning team act before the other team.

**Re-roll Initiative**: Each round starts fresh with new initiative rolls, keeping combat dynamic and unpredictable.

### Threat-Based Targeting

NPCs select targets using weighted random selection:
- **Base weight**: 10 + (threat × 2)
- **Low HP bonus**: 1.5× weight if HP < 25% of max

### NPC AI Behavior

NPCs make intelligent decisions based on their current state and class:

**Decision Priority:**
1. **Very Low HP (< 20%)**: 50% chance to attempt fleeing
2. **Low HP (< 40%)**: Try to heal using:
   - Healing potions from inventory
   - Healing spells (Clerics)
   - Self-healing abilities (Second Wind for Warriors)
3. **Offensive Spells**: Mages and Clerics have 70% chance to cast damage spells instead of basic attack
4. **Default**: Basic weapon attack

**AI Features:**
- NPCs use healing potions when health is low
- Spellcaster NPCs cast appropriate spells
- Warriors use Second Wind ability when available
- NPCs attempt to flee when near death
- NPCs intelligently select highest-level spells available

### Action Types

| Action | Description |
|--------|-------------|
| attack | d20 + STR mod + weapon hit bonus vs AC, damage = weapon dice + STR mod |
| defend | +2 AC until next turn |
| dodge | Attackers have disadvantage until next turn |
| flee | 50% chance to escape combat |
| spell | Cast a spell (requires spell slots) |
| ability | Use class ability |
| item | Use consumable item |
| pass | Skip turn |

### Advantage and Disadvantage

Attacks can have advantage (roll 2d20, take higher) or disadvantage (roll 2d20, take lower). Multiple sources of advantage/disadvantage cancel out.

**Attacker has advantage when target is:**
- Stunned
- Paralyzed (also auto-crits on hit)
- Blinded

**Attacker has disadvantage when target is:**
- Dodging
- Invisible

**Attacker has disadvantage when attacker is:**
- Blinded
- Poisoned
- Frightened
- Attacking at long range (ranged weapons/thrown weapons)

**Attacker has advantage when attacker is:**
- Invisible

### Ranged Combat

Distance between combatants is calculated from their character positions (each grid square = 5 feet). Attacks are checked against weapon range:

| Weapon Type | Normal Range | Long Range | Notes |
|-------------|--------------|------------|-------|
| Melee | 5 feet | - | Cannot attack beyond melee range |
| Melee + Reach | 10 feet | - | Extended melee range |
| Thrown | Varies | 2-3× normal | Can melee at close range or throw |
| Ranged | Varies | Varies | Specified in weapon range (e.g., "80/320") |

**Range Behavior:**
- **Within normal range**: Attack as normal
- **Beyond normal, within long range**: Attack with disadvantage
- **Beyond long range**: Attack fails ("target out of range")
- **Thrown weapons**: Use melee at ≤5 feet, thrown beyond that

**Range Examples:**
- Dagger: Melee (5 feet) or thrown (20/60 feet)
- Longbow: 150 feet normal, 600 feet long range
- Spear: Melee (5 feet) or thrown (30/120 feet)

**Spell Range:**
Spells have a range in feet. If the target is beyond the spell's range, casting fails.

### Attack Resolution

1. Check equipped weapon (main_hand or off_hand slot)
2. Roll d20 + attacker's STR modifier + weapon hit bonus
3. Compare to target's armor class
4. If roll ≥ AC (or natural 20): hit
5. Damage = weapon damage dice + STR modifier
   - **With weapon**: Uses weapon's `damage_dice` (e.g., 1d8 for longsword)
   - **Unarmed**: Uses 1d4
6. Critical hit (natural 20): double dice damage
7. Apply damage to target's HP
8. Sync damage to character record (persists after combat)
9. If HP ≤ 0: target falls unconscious (death saving throws begin)

### Death Saving Throws

When a character drops to 0 HP, they don't die immediately. Instead, they fall **unconscious** and begin making death saving throws.

#### Death Save Mechanics

| Situation | Result |
|-----------|--------|
| Roll 10+ | Success (need 3 to stabilize) |
| Roll 9 or less | Failure (3 failures = death) |
| Natural 20 | Wake up immediately with 1 HP |
| Natural 1 | Counts as 2 failures |
| Damage while unconscious | Automatic failure (melee crit = 2 failures) |
| Any healing | Wake up with healed HP |

#### Character Status

| Status | Description |
|--------|-------------|
| alive | Normal functioning character |
| unconscious | At 0 HP, making death saves |
| dead | 3 death save failures |

#### Death Save Processing

- Death saves are rolled automatically at the **start of an unconscious character's turn**
- Stabilized characters (3 successes) no longer make death saves but remain at 0 HP
- Any healing immediately wakes the character and resets death saves
- Damage to unconscious characters automatically causes death save failures

#### Related Character Fields

| Field | Description |
|-------|-------------|
| death_save_successes | Count of successful death saves (0-3) |
| death_save_failures | Count of failed death saves (0-3) |
| is_stable | Whether character has stabilized (3 successes) |
| status | Character status (alive, unconscious, dead) |

### Endpoints

#### Start Combat
```http
POST /combat/start
Content-Type: application/json

{
  "participants": [
    {"character_id": 1, "team_id": 1},
    {"character_id": 2, "team_id": 1},
    {"character_id": 3, "team_id": 2},
    {"character_id": 4, "team_id": 2}
  ],
  "zone_id": 1
}
```

**Response:**
```json
{
  "id": 1,
  "status": "in_progress",
  "round_number": 1,
  "current_turn": 0,
  "combatants": [...],
  "turn_order": [3, 1, 4, 2]
}
```

#### Process Turns
```http
POST /combat/{id}/process
```

Processes NPC turns automatically until a player needs to act.

**Response:**
```json
{
  "actions_taken": [...],
  "combatants": [...],
  "status": "awaiting_player",
  "awaiting_player": {"id": 1, "name": "Hero", ...},
  "combat_ended": false
}
```

#### Submit Player Action
```http
POST /combat/{id}/act
Content-Type: application/json

{
  "character_id": 1,
  "action_type": "attack",
  "target_id": 3
}
```

#### Get Combat State
```http
GET /combat/{id}
```

#### Resolve Combat
```http
POST /combat/{id}/resolve
```

Returns experience earned and loot.

#### Finish Combat
```http
POST /combat/{id}/finish
```

Returns complete combat summary.

#### Get Combat History
```http
GET /combat/{id}/history
```

Returns all actions taken during combat.

---

## Reference Data

The reference system provides pre-built game data that can be queried and used to create items.

### Base Weapons

The system includes 37 standard weapons from the SRD, stored in `data/weapons.json`.

#### Weapon Categories

| Category | Examples |
|----------|----------|
| simple_melee | Club, Dagger, Handaxe, Mace, Quarterstaff, Spear |
| simple_ranged | Crossbow (light), Dart, Shortbow, Sling |
| martial_melee | Battleaxe, Greatsword, Longsword, Rapier, Warhammer |
| martial_ranged | Crossbow (hand/heavy), Longbow, Blowgun |

#### Weapon Properties

| Property | Description |
|----------|-------------|
| ammunition | Requires ammunition; has range |
| finesse | Can use DEX instead of STR for attack/damage |
| reach | Adds 5 feet to melee attack range |
| thrown | Can be thrown for ranged attack using STR |
| two-handed | Requires two hands to use |
| versatile | Can be used one or two-handed for different damage |
| special | Has special rules |

### Endpoints

#### List All Weapons
```http
GET /reference/weapons
```

#### Filter Weapons
```http
GET /reference/weapons?category=martial_melee&max_cost_gp=20&property=versatile
```

**Query Parameters:**

| Parameter | Description |
|-----------|-------------|
| category | Filter by category (simple_melee, simple_ranged, martial_melee, martial_ranged) |
| max_cost_gp | Maximum cost in gold pieces |
| min_cost_gp | Minimum cost in gold pieces |
| damage_type | Filter by damage type (bludgeoning, piercing, slashing) |
| property | Filter by property (finesse, thrown, two-handed, etc.) |
| search | Search weapon names |

#### Get Specific Weapon
```http
GET /reference/weapons/longsword
```

**Response:**
```json
{
  "name": "Longsword",
  "category": "martial_melee",
  "cost_gp": 15,
  "cost_display": "15 gp",
  "damage_dice": "1d8",
  "damage_type": "slashing",
  "weight": 3.0,
  "properties": ["versatile"],
  "versatile_dice": "1d10"
}
```

#### List Categories
```http
GET /reference/weapons/categories/list
```

#### List Properties
```http
GET /reference/weapons/properties/list
```

### Example: Find Affordable Finesse Weapons
```http
GET /reference/weapons?property=finesse&max_cost_gp=25
```

Returns: Dagger (2 gp), Dart (5 cp), Rapier (25 gp), Scimitar (25 gp), Shortsword (10 gp), Whip (2 gp)

### Weapon Properties in Combat

The combat system implements special weapon properties:

| Property | Effect |
|----------|--------|
| **finesse** | Use the better of STR or DEX modifier for attack and damage rolls |
| **versatile** | When wielded two-handed (no off-hand item), uses the larger damage dice specified in `versatile_dice` |
| **thrown** | Can be thrown as a ranged attack using the weapon's range |
| **reach** | Extends melee range from 5 feet to 10 feet |
| **two-handed** | Requires both hands to wield |
| **ammunition** | Ranged weapon requiring ammunition |

**Examples:**
- **Dagger** (finesse, thrown): Rogue uses DEX +3 instead of STR +1 for attack/damage; can throw at 20/60 feet
- **Longsword** (versatile 1d10): Deals 1d8 one-handed, 1d10 when wielded two-handed
- **Glaive** (reach, two-handed): Can attack targets up to 10 feet away

### Base Armor

The system includes 13 standard armor types stored in `data/armor.json`.

#### Armor Categories

| Category | AC Calculation | Description |
|----------|----------------|-------------|
| light | base_ac + DEX mod | Flexible, no movement penalty |
| medium | base_ac + DEX mod (max 2) | Balanced protection and mobility |
| heavy | base_ac (no DEX) | Maximum protection |
| shield | +2 AC bonus | Held in one hand, stacks with armor |

#### Endpoints

```http
GET /reference/armor                        # List all armor
GET /reference/armor?category=heavy         # Filter by category
GET /reference/armor?stealth_ok=true        # Armor without stealth disadvantage
GET /reference/armor?max_cost_gp=100        # Filter by cost
GET /reference/armor/{name}                 # Get specific armor
GET /reference/armor/categories/list        # List categories
```

**Query Parameters:**

| Parameter | Description |
|-----------|-------------|
| category | Filter by category (light, medium, heavy, shield) |
| max_cost_gp | Maximum cost in gold pieces |
| min_cost_gp | Minimum cost in gold pieces |
| min_ac | Minimum base AC |
| stealth_ok | Set to true to exclude armor with stealth disadvantage |
| search | Search armor names |

#### Example Response
```json
{
  "name": "Chain Mail",
  "category": "heavy",
  "cost_gp": 75,
  "cost_display": "75 gp",
  "base_ac": 16,
  "max_dex_bonus": 0,
  "weight": 55.0,
  "stealth_disadvantage": true
}
```

### Consumables

The system includes 11 consumables stored in `data/consumables.json`.

#### Consumable Types

| Effect Type | Description | Examples |
|-------------|-------------|----------|
| heal | Restore HP | Healing Potion (2d4+2), Greater (4d4+4), Superior (8d4+8), Supreme (10d4+20) |
| damage | Deal damage when thrown | Alchemist's Fire (1d4 fire), Acid Vial (2d6 acid), Holy Water (2d6 radiant vs undead) |
| buff | Grant temporary status | Potion of Strength (+4 STR), Potion of Speed (hasted), Potion of Invisibility |
| cure | Remove conditions | Antidote (cures poisoned) |

#### Using Consumables in Combat

```http
POST /combat/{id}/act
Content-Type: application/json

{
  "character_id": 1,
  "action_type": "item",
  "item_id": 5,
  "target_id": 2
}
```

- The `item_id` must be an inventory item ID (not the item definition ID)
- Consumables are removed/decremented after use
- Healing consumables can target self if no target specified

#### Endpoints

```http
GET /reference/consumables                     # List all consumables
GET /reference/consumables?effect_type=heal   # Filter by effect type
GET /reference/consumables?rarity=rare        # Filter by rarity
GET /reference/consumables/{name}             # Get specific consumable
```

### Status Effects

The system includes 15 status effects stored in `data/status_effects.json`.

#### Effect Categories

**Harmful Effects:**

| Effect | Duration | Description |
|--------|----------|-------------|
| poisoned | 3 rounds | 1d4 poison damage/turn, attack disadvantage |
| burning | 2 rounds | 1d6 fire damage/turn |
| stunned | 1 round | Cannot act, attacks have advantage against |
| paralyzed | 1 round | Cannot act, melee hits auto-crit |
| blinded | 2 rounds | Attack disadvantage, attacks have advantage against |
| frightened | 3 rounds | Attack disadvantage |
| slowed | 3 rounds | -2 AC |
| cursed | 10 rounds | -1d4 to attack rolls |

**Beneficial Effects:**

| Effect | Duration | Description |
|--------|----------|-------------|
| hasted | 10 rounds | +2 AC, extra action |
| invisible | 10 rounds | Attack advantage, attacks have disadvantage against |
| blessed | 10 rounds | +1d4 to attack rolls |
| regenerating | 5 rounds | 1d4 healing/turn |
| defending | 1 round | +2 AC (from Defend action) |
| dodging | 1 round | Attacks have disadvantage against |

#### Status Effect Processing

- **Start of turn**: Damage over time (poison, burning) and healing over time (regenerating)
- **During turn**: Stunned/paralyzed characters auto-skip their turn
- **End of turn**: Durations tick down, expired effects are removed
- **Defending/Dodging**: Cleared at start of your next turn (not ticked down)

#### Endpoints

```http
GET /reference/status-effects                  # List all status effects
GET /reference/status-effects?harmful=true    # Filter harmful effects
GET /reference/status-effects?beneficial=true # Filter beneficial effects
GET /reference/status-effects/{id}            # Get specific effect
```

### Class Abilities

The system includes 14 class abilities stored in `data/class_abilities.json`.

#### Abilities by Class

**Warrior:**

| Ability | Min Level | Uses | Effect |
|---------|-----------|------|--------|
| Second Wind | 1 | 1/short rest | Heal 1d10 + level HP |
| Action Surge | 2 | 1/short rest | Extra action this turn |

**Rogue:**

| Ability | Min Level | Uses | Effect |
|---------|-----------|------|--------|
| Sneak Attack | 1 | 1/turn | +Nd6 damage (N = level/2, rounded up) |
| Cunning Action | 2 | Unlimited | Bonus action: Dash, Disengage, or Hide |
| Evasion | 7 | Passive | Take no damage on successful DEX save |

**Cleric:**

| Ability | Min Level | Uses | Effect |
|---------|-----------|------|--------|
| Channel Divinity: Preserve Life | 2 | 1/short rest | Heal allies for 5× level HP total |
| Turn Undead | 2 | 1/short rest | Frighten undead enemies |
| Divine Intervention | 10 | 1/long rest | Powerful random effect (level% chance) |

**Mage:**

| Ability | Min Level | Uses | Effect |
|---------|-----------|------|--------|
| Arcane Recovery | 1 | 1/long rest | Recover spell slots (level/2 total levels) |
| Spell Mastery | 18 | Passive | Cast 1st/2nd level spell at will |

**Ranger:**

| Ability | Min Level | Uses | Effect |
|---------|-----------|------|--------|
| Hunter's Mark | 1 | 2/long rest | +1d6 damage to marked target |
| Natural Explorer | 1 | Passive | Advantage on initiative |
| Favored Enemy | 1 | Passive | +2 damage vs chosen enemy type |
| Multiattack | 5 | Passive | Two attacks per Attack action |

#### Using Abilities in Combat

```http
POST /combat/{id}/act
Content-Type: application/json

{
  "character_id": 1,
  "action_type": "ability",
  "ability_id": "second_wind"
}
```

- Ability uses are restored on short or long rest (depending on ability)
- Some abilities require a target (sneak_attack, hunters_mark)
- Passive abilities are always active (no action required)

#### Endpoints

```http
GET /reference/abilities                       # List all abilities
GET /reference/abilities?character_class=warrior  # Filter by class
GET /reference/abilities?min_level=5          # Available at level 5
GET /reference/abilities/{id}                 # Get specific ability
GET /reference/abilities/class/{class_name}   # Get abilities for class at level
```

### Terrain Effects

The system includes terrain effects stored in `data/terrain_effects.json`.

#### Terrain Properties

| Property | Description |
|----------|-------------|
| movement_cost | How many movement points to enter (0 = impassable) |
| passable | Whether characters can enter this terrain |
| hazardous | Deals damage when entering or staying |
| damage_on_enter | Damage dealt when entering |
| damage_per_turn | Damage dealt each turn while in this terrain |
| cover_bonus | AC bonus when targeted in combat |
| effects | Status effects that may be applied |

#### Endpoints

```http
GET /reference/terrain                       # List all terrain types
GET /reference/terrain?hazardous=true        # Filter hazardous terrain
GET /reference/terrain?provides_cover=true   # Terrain with cover bonus
GET /reference/terrain?difficult=true        # Difficult terrain (cost > 1)
GET /reference/terrain/{terrain_type}        # Get specific terrain
```

#### Example Response
```json
{
  "terrain_type": "forest",
  "name": "Dense Forest",
  "description": "Thick vegetation that slows movement but provides cover.",
  "movement_cost": 2,
  "passable": true,
  "hazardous": false,
  "damage_on_enter": 0,
  "damage_per_turn": 0,
  "damage_type": null,
  "cover_bonus": 2,
  "effects": []
}
```

---

## Monster System

The system includes 24 pre-built monster templates stored in `data/monsters.json` that can be used to quickly create NPC enemies for encounters.

### Monster Types

| Type | Description | Examples |
|------|-------------|----------|
| humanoid | Two-legged beings with human-like intelligence | Goblin, Orc, Bandit, Hobgoblin |
| undead | Once-living creatures animated by dark magic | Skeleton, Zombie, Ghoul, Wight |
| beast | Natural animals and their giant variants | Wolf, Giant Rat, Dire Wolf, Giant Spider |
| giant | Huge humanoid creatures of great strength | Ogre, Troll |
| monstrosity | Unnatural creatures born of magic or curses | Owlbear, Minotaur |
| fiend | Evil creatures from the lower planes | Imp |
| dragon | Ancient reptilian creatures of immense power | Young Dragon, Adult Dragon |

### Monster Properties

| Property | Description |
|----------|-------------|
| id | Unique identifier for the monster |
| name | Display name |
| size | tiny, small, medium, large, huge |
| type | humanoid, undead, beast, giant, monstrosity, fiend, dragon |
| challenge_rating | Difficulty rating (0.125 to 14+) |
| experience_reward | XP awarded when defeated |
| base_hp | Starting hit points |
| armor_class | AC for combat |
| strength/dexterity/etc. | Ability scores |
| attacks | Available attacks with damage and hit bonus |
| special_abilities | Unique abilities (pack_tactics, regeneration, etc.) |
| vulnerabilities | Damage types that deal extra damage |
| immunities | Damage types that deal no damage |
| condition_immunities | Status effects that don't apply |

### Challenge Rating Guide

| CR | XP | Typical Monsters |
|----|-----|------------------|
| 0.125 | 25 | Giant Rat, Bandit, Cultist |
| 0.25 | 50 | Goblin, Skeleton, Zombie, Wolf |
| 0.5 | 100 | Orc, Hobgoblin, Gnoll |
| 1 | 200 | Bugbear, Dire Wolf, Ghoul, Giant Spider, Imp |
| 2 | 450 | Ogre, Bandit Captain |
| 3 | 700 | Owlbear, Minotaur, Wight |
| 5 | 1800 | Troll |
| 7 | 2900 | Young Dragon |
| 14 | 11500 | Adult Dragon |

### Endpoints

#### List All Monsters
```http
GET /reference/monsters
```

#### Filter Monsters
```http
GET /reference/monsters?monster_type=undead&max_cr=1&size=medium
```

**Query Parameters:**

| Parameter | Description |
|-----------|-------------|
| monster_type | Filter by type (humanoid, undead, beast, etc.) |
| size | Filter by size (tiny, small, medium, large, huge) |
| min_cr | Minimum challenge rating |
| max_cr | Maximum challenge rating |
| search | Search monster names |

#### Get Specific Monster
```http
GET /reference/monsters/goblin
```

**Response:**
```json
{
  "id": "goblin",
  "name": "Goblin",
  "size": "small",
  "type": "humanoid",
  "challenge_rating": 0.25,
  "experience_reward": 50,
  "hit_dice": "2d6",
  "base_hp": 7,
  "armor_class": 15,
  "speed": 30,
  "strength": 8,
  "dexterity": 14,
  "constitution": 10,
  "intelligence": 10,
  "wisdom": 8,
  "charisma": 8,
  "attacks": [
    {"name": "Scimitar", "damage_dice": "1d6", "damage_type": "slashing", "hit_bonus": 4},
    {"name": "Shortbow", "damage_dice": "1d6", "damage_type": "piercing", "hit_bonus": 4, "range": "80/320"}
  ],
  "special_abilities": ["nimble_escape"],
  "description": "Small, sneaky humanoids that often attack in groups."
}
```

#### List Monster Types
```http
GET /reference/monsters/types/list
```

#### Get Monsters by Challenge Rating
```http
GET /reference/monsters/by-cr/0.5
```

### Creating Characters from Monster Templates

Create an NPC character directly from a monster template:

```http
POST /character/from-monster/goblin?name=Goblin%20Scout
```

This creates a new NPC with:
- Monster's ability scores (STR, DEX, CON, INT, WIS, CHA)
- Monster's HP and AC
- A character class mapped from monster type (for ability purposes)

**Response:**
```json
{
  "id": 5,
  "name": "Goblin Scout",
  "character_class": "warrior",
  "character_type": "npc",
  "strength": 8,
  "dexterity": 14,
  "current_hp": 7,
  "max_hp": 7,
  "armor_class": 15
}
```

### Example: Creating an Encounter

```python
import httpx

# Create monsters for an encounter
goblin1 = httpx.post("/character/from-monster/goblin?name=Goblin%20Warrior").json()
goblin2 = httpx.post("/character/from-monster/goblin?name=Goblin%20Archer").json()
bugbear = httpx.post("/character/from-monster/bugbear?name=Bugbear%20Chief").json()

# Start combat with player vs monsters
combat = httpx.post("/combat/start", json={
    "participants": [
        {"character_id": player_id, "team_id": 1},
        {"character_id": goblin1["id"], "team_id": 2},
        {"character_id": goblin2["id"], "team_id": 2},
        {"character_id": bugbear["id"], "team_id": 2}
    ]
}).json()
```

---

## Loot Tables

The system includes 16 loot tables stored in `data/loot_tables.json` that define what items and gold drop from defeated enemies.

### Loot Table Structure

| Property | Description |
|----------|-------------|
| id | Unique identifier for the loot table |
| name | Display name |
| description | Description of the loot source |
| gold_range | [min, max] gold dropped |
| items | Weighted list of possible item drops |
| guaranteed_drops | Items that always drop |
| drop_count | {min, max} number of random items to roll |

### Monster Loot Mappings

| Monster | Loot Table | Gold Range |
|---------|------------|------------|
| Goblin | goblin_basic | 1-10 |
| Skeleton | skeleton_basic | 0-5 |
| Zombie | zombie_basic | 0-3 |
| Orc | orc_warrior | 5-25 |
| Bugbear | bugbear_chief | 20-50 |
| Bandit | bandit_basic | 5-20 |
| Bandit Captain | bandit_captain | 30-75 |
| Ogre | ogre_brute | 10-40 |
| Troll | troll_giant | 50-150 |
| Young Dragon | young_dragon | 200-500 |
| Adult Dragon | adult_dragon | 1000-3000 |

Some monsters (wolves, beasts, imps) don't have loot tables.

### Loot Rolling

Loot is automatically rolled when combat ends and winners are determined:
1. Each defeated enemy with a loot table has their loot rolled
2. Gold from all enemies is summed and awarded to the winning team
3. Items are collected and returned in the combat resolution

### Endpoints

#### List All Loot Tables
```http
GET /reference/loot-tables
```

#### Get Specific Loot Table
```http
GET /reference/loot-tables/goblin_basic
```

#### Get Loot Table for Monster
```http
GET /reference/loot-tables/for-monster/goblin
```

Returns the loot table associated with a monster.

### Combat Resolution with Loot

When calling `/combat/{id}/resolve`, the response now includes loot:

```json
{
  "winner_team_id": 1,
  "experience_earned": {"1": 50},
  "level_ups": [],
  "loot": {
    "gold": 15,
    "items": [
      {"item_name": "Scimitar", "quantity": 1},
      {"item_name": "Dagger", "quantity": 2}
    ]
  }
}
```

Gold is automatically awarded to the first winner. Items are returned for manual distribution.

---

### Complete Combat Example

```python
import httpx

# Create characters
hero = httpx.post("/character/", json={
    "name": "Hero",
    "character_class": "warrior",
    "character_type": "player"
}).json()

goblin = httpx.post("/character/", json={
    "name": "Goblin",
    "character_class": "rogue",
    "character_type": "npc"
}).json()

# Start combat
combat = httpx.post("/combat/start", json={
    "participants": [
        {"character_id": hero["id"], "team_id": 1},
        {"character_id": goblin["id"], "team_id": 2}
    ]
}).json()

session_id = combat["id"]

# Combat loop
while True:
    # Process NPC turns
    result = httpx.post(f"/combat/{session_id}/process").json()

    if result["combat_ended"]:
        break

    if result["status"] == "awaiting_player":
        # Find enemy to attack
        enemies = [c for c in result["combatants"]
                   if c["team_id"] != 1 and c["is_alive"]]

        if enemies:
            # Attack first enemy
            httpx.post(f"/combat/{session_id}/act", json={
                "character_id": hero["id"],
                "action_type": "attack",
                "target_id": enemies[0]["id"]
            })

# Get final results
summary = httpx.post(f"/combat/{session_id}/finish").json()
print(f"Winner: Team {summary['winner_team_id']}")
print(f"Total rounds: {summary['total_rounds']}")
```

---

## Web Application

A browser-based frontend is included in the `webapp/` directory for interacting with the API graphically.

### Running the Webapp

1. Start the API server:
```bash
uvicorn src.main:app --reload --port 8000
```

2. Open the webapp:
   - Open `webapp/index.html` directly in your browser, or
   - Serve it with a simple HTTP server:
```bash
cd webapp && python -m http.server 8080
```
   Then visit `http://localhost:8080`

### Features

| Tab | Functionality |
|-----|---------------|
| **Characters** | Create/list/delete characters, view attributes and skills, manage HP |
| **Inventory** | Create items with weapon/armor properties, manage character inventories, equip/unequip, browse base weapons reference |
| **Location** | Create zones, view grid map, move characters |
| **Quests** | Create quests with objectives, assign to characters, track progress |
| **Combat** | Start combat sessions, process turns, submit player actions (attack/defend/flee) |
| **Scenarios** | Create scenarios with weighted outcomes, trigger for characters |
| **Events** | View game event log with filtering |

### Base Weapons Browser

The Inventory tab includes a **Base Weapons Reference** panel that:
- Displays all 37 standard weapons from the SRD
- Filters by category, max cost, and properties
- Search by weapon name
- **"Add to DB"** button creates an item from the weapon template

### Screenshots

The webapp uses a dark theme with:
- Tabbed navigation
- Form-based input for creating entities
- Real-time feedback via toast notifications
- Combat arena with health bars and action buttons

---

## Database Migrations

This project uses Alembic for database migrations.

### Create a New Migration

```bash
alembic revision --autogenerate -m "Description of changes"
```

### Apply Migrations

```bash
alembic upgrade head
```

### Rollback Migration

```bash
alembic downgrade -1
```

---

## Testing

Run all tests:

```bash
pytest
```

Run with verbose output:

```bash
pytest -v
```

Run specific test file:

```bash
pytest tests/test_character.py
```

Run specific test:

```bash
pytest tests/test_combat.py::TestCombatFlow::test_player_action
```

### Test Coverage

The test suite includes 57 tests covering:

- Character CRUD and sub-resources
- Inventory management and equipment
- Armor AC bonus application (equip/unequip/replace)
- Location and spatial queries
- Quest assignment and progress
- Event logging
- Scenario triggering
- Combat initialization, flow, and HP synchronization

---

## Project Structure

```
tabletop-rpg-api/
├── src/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Configuration settings
│   ├── database.py          # SQLAlchemy setup
│   ├── core/                # Shared utilities
│   │   ├── enums.py         # Enumeration types
│   │   └── exceptions.py    # Custom exceptions
│   ├── character/           # Character module
│   │   ├── models.py        # SQLAlchemy models
│   │   ├── schemas.py       # Pydantic schemas
│   │   ├── service.py       # Business logic
│   │   └── router.py        # API endpoints
│   ├── inventory/           # Inventory module
│   ├── location/            # Location module
│   ├── quest/               # Quest module
│   ├── event/               # Event module
│   ├── scenario/            # Scenario module
│   ├── combat/              # Combat module
│   └── reference/           # Reference data module
│       └── router.py        # Base weapons API
├── data/
│   ├── weapons.json         # Base weapon definitions (37 weapons)
│   ├── armor.json           # Base armor definitions (13 armor types)
│   ├── spells.json          # Spell definitions (16 spells)
│   ├── consumables.json     # Consumable items (11 items)
│   ├── status_effects.json  # Status effect definitions (15 effects)
│   ├── class_abilities.json # Class abilities (14 abilities)
│   ├── terrain_effects.json # Terrain effect definitions (10 types)
│   ├── monsters.json        # Monster templates (24 monsters)
│   └── loot_tables.json     # Loot table definitions (16 tables)
├── webapp/
│   ├── index.html           # Main HTML structure
│   ├── styles.css           # Dark theme styling
│   └── app.js               # API interactions
├── tests/                   # Test suite
├── alembic/                 # Database migrations
├── pyproject.toml           # Project configuration
├── requirements.txt         # Dependencies
├── README.md                # This file
└── TODO.md                  # Feature roadmap and todo list
```

---

## Admin Endpoints

### Reset Database

Reset the database to a clean state (clears all player data but keeps game content):

```http
POST /admin/reset
```

This endpoint:
- Clears all characters, combat sessions, inventory, quest assignments, and game events
- Preserves quests, zones, exits, scenarios, and items (game content)
- Useful for testing or starting fresh

The webapp includes a "Reset Database" button in the admin panel.

---

## Tech Stack

- **Framework**: FastAPI
- **ORM**: SQLAlchemy
- **Database**: SQLite (easily switchable to PostgreSQL)
- **Migrations**: Alembic
- **Validation**: Pydantic v2
- **Testing**: pytest

---

## License

MIT License
