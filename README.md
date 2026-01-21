# Dungeons and Agents

A voice-driven tabletop RPG built with LiveKit agents, featuring real-time speech interaction, dynamic storytelling, and classic D&D-style mechanics.

[![Dungeons and Agents Demo](https://img.youtube.com/vi/2h2fSNHd1E4/0.jpg)](https://youtu.be/2h2fSNHd1E4)

## Overview

**Dungeons and Agents** is a voice-first RPG experience where players interact with an AI dungeon master through natural speech. The system features:

- **Voice-First Gameplay**: Speak your actions naturally - "I want to talk to the barkeep" or "Attack the goblin with my sword"
- **Multi-Agent System**: Seamless switching between a dramatic narrator agent and an action-focused combat agent
- **Classic RPG Mechanics**: D20 dice rolling, skill checks, turn-based combat with initiative, spell casting
- **Dynamic NPCs**: AI-generated characters with unique personalities, inventories, and voice acting
- **Quest System**: LLM-driven quest progression where the AI tracks your actions and updates objectives
- **Persistent State**: Character progression, inventory management, and story tracking

## Architecture

The project consists of three main components:

```
┌─────────────────────┐     LiveKit RPC     ┌─────────────────────┐     HTTP API     ┌─────────────────────┐
│                     │ ◄─────────────────► │                     │ ◄──────────────► │                     │
│   Web Frontend      │                     │   Voice Agent       │                  │   RPG Backend       │
│   (Next.js)         │                     │   (Python/LiveKit)  │                  │   (FastAPI)         │
│                     │                     │                     │                  │                     │
│ • Game UI           │                     │ • Speech-to-Text    │                  │ • Game State DB     │
│ • Character status  │                     │ • LLM Processing    │                  │ • Combat Engine     │
│ • Quest display     │                     │ • Text-to-Speech    │                  │ • Quest Storage     │
│ • Voice chat        │                     │ • Agent Switching   │                  │ • Character CRUD    │
│                     │                     │ • Quest Management  │                  │ • Dice Mechanics    │
└─────────────────────┘                     └─────────────────────┘                  └─────────────────────┘
     role-playing/                               role-playing/                           rpg-backend/
   role_playing_frontend/
```

| Component | Directory | Description |
|-----------|-----------|-------------|
| **Voice Agent** | `role-playing/` | LiveKit-based voice agent with narrator and combat modes |
| **Web Frontend** | `role-playing/role_playing_frontend/` | Next.js UI for game status, portraits, and voice interaction |
| **RPG Backend** | `rpg-backend/` | FastAPI server handling all game mechanics and state |

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ and pnpm
- LiveKit Cloud Account

### 1. Start the RPG Backend

```bash
cd rpg-backend
pip install -e ".[dev]"
python -m src.seed          # Seed initial game content
uvicorn src.main:app --reload --port 8000
```

### 2. Start the Voice Agent

```bash
cd role-playing
pip install -r requirements.txt

# Set up environment variables in .env:
# LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
# OPENAI_API_KEY, DEEPGRAM_API_KEY, INWORLD_API_KEY
# RPG_API_BASE_URL=http://localhost:8000

python agent.py dev
```

### 3. Start the Web Frontend

```bash
cd role-playing/role_playing_frontend
pnpm install
pnpm dev
```

Open http://localhost:3000 in your browser and start playing!

## How to Play

### Character Creation
When you first connect, the narrator guides you through creating your character:
- Say your character's name
- Choose a class: Warrior, Mage, Rogue, or Cleric

### Exploration
- **"Look around"** - Get a description of your surroundings
- **"Go to the market"** or **"Head north"** - Move to new locations
- **"Talk to the barkeep"** - Interact with NPCs
- **"Check my inventory"** - See what you're carrying

### Combat
When combat begins, the system automatically switches to the combat agent:
- **"Attack the goblin"** - Strike an enemy
- **"Cast fireball"** - Use a spell (mages/clerics)
- **"Defend"** - Take a defensive stance
- **"Flee"** - Attempt to escape

### Quests
The AI narrator tracks your progress through quests:
- Talk to NPCs to discover quest objectives
- Complete objectives by exploring, fighting, or interacting
- The narrator announces when you complete objectives and quests

## Project Structure

```
tabletop/
├── role-playing/                    # Voice agent and frontend
│   ├── agent.py                    # Main entry point
│   ├── agents/                     # Narrator and combat agents
│   ├── api/                        # HTTP client for RPG backend
│   ├── services/                   # Quest, exploration, story services
│   ├── core/                       # Game state and settings
│   ├── generators/                 # AI-driven NPC/item generation
│   ├── prompts/                    # Agent instruction prompts
│   └── role_playing_frontend/      # Next.js web UI
│
├── rpg-backend/                     # Game mechanics API
│   ├── src/                        # FastAPI modules
│   │   ├── character/              # Character management
│   │   ├── combat/                 # Combat engine
│   │   ├── quest/                  # Quest system
│   │   ├── inventory/              # Item management
│   │   ├── location/               # Zone/grid system
│   │   └── reference/              # Game data (weapons, spells, etc.)
│   ├── data/                       # JSON reference data
│   └── webapp/                     # Admin panel
│
└── README.md                        # This file
```

## Documentation

Each component has detailed documentation:

- **[Voice Agent README](role-playing/README.md)** - Full gameplay guide, commands, and agent architecture
- **[Architecture Details](role-playing/architecture_README.md)** - Technical deep-dive into the agent system
- **[Frontend README](role-playing/role_playing_frontend/README.md)** - UI setup and RPC communication
- **[Backend API README](rpg-backend/README.md)** - Complete API documentation with all endpoints

## Key Features

### LLM-Driven Quest System

Unlike traditional games with hardcoded triggers, the AI narrator decides when to progress quests:

```
Player: "I'll talk to the barkeep about the rumors"
Agent:  1. Calls interact_with_npc(npc_type="barkeep", action="talk")
        2. Calls get_active_quests() to check current objectives
        3. Sees "Talk to the barkeep" objective
        4. Calls progress_quest_objective(quest_id=1, objective_id=1)
        5. Narrates the interaction with voice acting
```

### Multi-Agent Architecture

The system seamlessly switches between agents based on context:
- **Narrator Agent**: Handles exploration, dialogue, skill checks, and quest management
- **Combat Agent**: Manages turn-based combat with initiative, attacks, spells, and abilities

### Voice Acting

NPCs speak with distinct AI-generated voices using Inworld TTS:
- Timothy (energetic) - Merchants, barkeeps
- Dennis (gruff) - Guards, warriors
- Ashley (calm) - Healers, sages
- Deborah (mature) - Innkeepers, nobles
- Olivia (young) - Travelers, young NPCs

## Tech Stack

| Layer | Technology |
|-------|------------|
| Voice Agent | LiveKit Agents |
| Speech-to-Text | Deepgram |
| Text-to-Speech | Inworld AI |
| LLM | OpenAI Gpt 4.1 |
| Web Frontend | Next.js, React, Tailwind CSS |
| Backend API | FastAPI, SQLAlchemy, SQLite |
