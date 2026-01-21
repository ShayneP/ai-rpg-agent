# Dungeons and Agents - RPG Game Architecture

This is a modular, extensible RPG game built with LiveKit Agents. The architecture emphasizes dynamic content generation using LLMs while maintaining clean code organization.

## Architecture Overview

```
role-playing/
├── agent.py                 # Main entry point and RPC handlers
├── agents/                  # Agent implementations
│   ├── base_agent.py       # Base class for all agents
│   ├── narrator_agent.py   # Handles exploration, dialogue, and quests
│   └── combat_agent.py     # Handles combat encounters
├── core/                    # Core game state and configuration
│   ├── constants.py        # Shared deterministic constants (trades, voices)
│   ├── game_state.py       # Game state management (stores API IDs)
│   ├── state_service.py    # Async API fetch methods for game state
│   └── settings.py         # Provider/model/voice defaults + API URL
├── api/                     # RPG API client
│   ├── client.py           # Async HTTP clients (Location, Quest, Scenario, etc.)
│   └── models.py           # Pydantic response models
├── services/                # Service layer for API operations
│   ├── exploration.py      # Zone navigation via API
│   ├── player.py           # Character creation and management
│   ├── quests.py           # Quest serialization and formatting
│   ├── scenarios.py        # Scenario triggers and effects
│   └── story.py            # Unified story management via API
├── generators/              # Dynamic content generation
│   ├── npc_generator.py    # NPC creation with LLM
│   └── item_generator.py   # Item generation with LLM
├── rules/                   # YAML rule files
│   ├── npc_generation_rules.yaml
│   ├── item_generation_rules.yaml
│   └── location_generation_rules.yaml
├── utils/                   # Utilities
│   └── display.py          # Console formatting
├── character.py             # Character classes
├── prompts/                 # Agent instruction prompts
└── role_playing_frontend/   # Next.js web frontend
```

## Key Features

### Dynamic Content Generation
- NPCs are generated dynamically with unique personalities, inventories, and backstories
- Items are created contextually based on location and owner
- Everything adapts to the current game state and recent events

### Quests and Scenarios (LLM-Driven)
- Quests and scenarios are stored in the database and accessed via API endpoints
- **LLM-driven quest progression**: The agent (not the API) decides when to progress quests
- The narrator agent has function tools for quest management:
  - `get_available_quests()` - List quests available to accept
  - `get_active_quests()` - Get current quests with objectives and IDs
  - `accept_quest()` - Accept a new quest
  - `progress_quest_objective()` - Update objective progress
  - `complete_quest()` - Finish a quest and claim rewards
  - `abandon_quest()` - Give up on a quest
- `services/quests.py` provides quest serialization and formatting for the frontend
- `services/scenarios.py` handles narrative triggers based on location, items, health, etc.
- `services/story.py` orchestrates story progression via API calls

### Database Seeding
- Initial game content (zones, exits, quests, scenarios) is seeded via the RPG backend's `src/seed.py`
- From the `rpg-backend/` directory, run `python -m src.seed` to populate the database
- Use `python -m src.seed --reseed` to clear and re-seed during development

### Configuration and Constants
- `core/settings.py` centralizes provider/model/voice defaults with environment overrides
- `core/constants.py` keeps shared deterministic values (trade values, TTS voices) in one place

### Modular Design
- Each agent handles specific game modes (exploration vs combat)
- Generators can be extended without modifying core code
- Rule files make it easy to adjust generation parameters

### Parallel LLM Processing
- Multiple aspects of NPCs (personality, inventory, backstory) are generated in parallel
- Efficient use of LLM resources for faster response times

## Adding New Features

### Adding a New NPC Type
1. Edit `rules/npc_generation_rules.yaml`
2. Add your NPC type with appropriate weights and guidelines
3. The generator will automatically use your new rules

### Adding New Items
1. Edit `rules/item_generation_rules.yaml`
2. Add new item categories or modify generation prompts
3. Items will be generated according to your specifications

### Adding New Quests
1. Add quest data in `rpg-backend/src/seed.py` in the `seed_quests()` function
2. Define objectives with `objective_type` and `target_identifier` to help the LLM track progress
3. From `rpg-backend/`, run `python -m src.seed --reseed` to update the database
4. The narrator agent uses function tools to progress quests based on player actions

### Adding New Scenarios
1. Add scenario data in `rpg-backend/src/seed.py` in the `seed_scenarios()` function
2. Define triggers (location, quest status, health threshold, etc.)
3. Define outcomes (narrative text, quest grants, health changes, etc.)
4. From `rpg-backend/`, run `python -m src.seed --reseed` to update the database

### Creating New Game Systems
1. Add a new file in `systems/`
2. Import and use it in the appropriate agent
3. Follow the pattern of existing systems for consistency

## Running the Game

```bash
python agent.py dev
```

## Future Enhancements
- Quest generation system
- Dynamic location descriptions
- Persistent world state
- Multiplayer support
- More sophisticated combat AI
- Spell creation system
- Crafting mechanics
