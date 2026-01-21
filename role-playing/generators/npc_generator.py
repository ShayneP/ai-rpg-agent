"""
---
title: NPC Generator
category: complex-agents
tags: [rpg, procedural-generation, character-creation, personality-generation]
difficulty: advanced
description: Fast NPC generation using a single LLM call + rule-based inventory
---
"""

import json
import random
import yaml
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from livekit.agents import inference
from livekit.agents.llm import ChatContext, ChatMessage

from character import NPCCharacter, CharacterClass, Item, create_random_npc
from core.settings import settings

logger = logging.getLogger("dungeons-and-agents")


class NPCGenerator:
    """Generates dynamic NPCs using a single LLM call + rule-based inventory"""
    
    def __init__(self):
        self.rules = self._load_rules()
    
    def _load_rules(self) -> dict:
        """Load NPC generation rules from YAML"""
        rules_path = Path(__file__).parent.parent / "rules" / "npc_generation_rules.yaml"
        try:
            with open(rules_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load NPC generation rules: {e}")
            return {}
    
    async def generate_npc(self, name: str, location: str, 
                          recent_events: List[str] = None,
                          npc_type: str = None) -> NPCCharacter:
        """Generate a complete NPC with a single LLM call + rule-based inventory"""
        
        # Determine NPC type from name if not specified
        if not npc_type:
            npc_type = self._determine_npc_type(name)
        
        # Get rules for this NPC type
        type_rules = self.rules.get('npc_types', {}).get(npc_type, {})
        if not type_rules:
            type_rules = self.rules.get('npc_types', {}).get('commoner', {
                'class_weights': {'warrior': 0.25, 'rogue': 0.25, 'cleric': 0.25, 'mage': 0.25},
                'level_range': [1, 3],
                'disposition_weights': {'friendly': 0.5, 'neutral': 0.5},
                'personality_traits': ['simple', 'friendly'],
                'gold_range': [10, 40],
            })
        
        # Determine class and level
        character_class = self._select_class(type_rules.get('class_weights', {'warrior': 1.0}))
        level = random.randint(*type_rules.get('level_range', [1, 3]))
        
        # Create base NPC
        npc = create_random_npc(
            name=name.title(),
            character_class=character_class,
            level=level,
            disposition=self._select_disposition(type_rules.get('disposition_weights', {'friendly': 1.0}))
        )
        
        # Set gold based on type
        npc.gold = random.randint(*type_rules.get('gold_range', [10, 40]))
        
        # Set merchant flag
        if npc_type == 'merchant':
            npc.merchant = True
        
        # Single LLM call to generate personality, backstory, and dialogue
        traits = random.sample(type_rules.get('personality_traits', ['friendly']), 
                               min(3, len(type_rules.get('personality_traits', ['friendly']))))
        
        generated = await self._generate_npc_content(
            npc.name, npc.character_class.value, npc_type, location, 
            recent_events or [], traits, type_rules.get('dialogue_style', '')
        )
        
        npc.personality = generated.get('personality', f"A {npc_type} with a {traits[0]} demeanor.")
        npc.backstory = generated.get('backstory', f"Works in the {location}.")
        npc.dialogue_options = generated.get('dialogue', [f"Hello, traveler."])
        
        # Rule-based inventory (no LLM call)
        npc.inventory = self._generate_inventory(npc_type, character_class.value, level)
        
        return npc
    
    def _determine_npc_type(self, name: str) -> str:
        """Determine NPC type from name"""
        name_lower = name.lower()
        
        if any(word in name_lower for word in ['barkeep', 'innkeeper', 'merchant', 'trader', 'shopkeeper']):
            return 'merchant'
        elif any(word in name_lower for word in ['guard', 'soldier', 'captain', 'knight']):
            return 'guard'
        elif any(word in name_lower for word in ['wizard', 'mage', 'sorcerer', 'enchanter']):
            return 'wizard'
        else:
            return 'commoner'
    
    def _select_class(self, class_weights: Dict[str, float]) -> CharacterClass:
        """Select character class based on weights"""
        classes = []
        weights = []
        
        for class_name, weight in class_weights.items():
            classes.append(CharacterClass[class_name.upper()])
            weights.append(weight)
        
        return random.choices(classes, weights=weights)[0]
    
    def _select_disposition(self, disposition_weights: Dict[str, float]) -> str:
        """Select disposition based on weights"""
        dispositions = list(disposition_weights.keys())
        weights = list(disposition_weights.values())
        return random.choices(dispositions, weights=weights)[0]
    
    async def _generate_npc_content(self, name: str, char_class: str, npc_type: str,
                                    location: str, recent_events: List[str],
                                    traits: List[str], dialogue_style: str) -> dict:
        """Single LLM call to generate personality, backstory, and dialogue"""
        
        events_str = ', '.join(recent_events[-3:]) if recent_events else 'nothing notable'
        traits_str = ', '.join(traits)
        
        prompt = f"""Generate content for {name}, a {char_class} {npc_type} in {location}.
Traits: {traits_str}. Recent events: {events_str}.
{f'Style: {dialogue_style}' if dialogue_style else ''}

Return JSON: {{"personality": "1-2 sentences", "backstory": "1-2 sentences", "dialogue": ["greeting1", "greeting2"]}}"""

        llm = inference.LLM(model=settings.llm_model)
        
        ctx = ChatContext([
            ChatMessage(type="message", role="system", 
                       content=["You are an RPG NPC generator. Return only valid JSON, be concise."]),
            ChatMessage(type="message", role="user", content=[prompt])
        ])
        
        response = ""
        async with llm.chat(chat_ctx=ctx) as stream:
            async for chunk in stream:
                if not chunk:
                    continue
                content = getattr(chunk.delta, 'content', None) if hasattr(chunk, 'delta') else str(chunk)
                if content:
                    response += content
        
        # Parse JSON response
        try:
            # Try to extract JSON from response
            text = response.strip()
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except Exception as e:
            logger.warning(f"Failed to parse NPC content JSON: {e}")
        
        # Fallback
        return {
            'personality': f"A {npc_type} with a {traits[0] if traits else 'calm'} demeanor.",
            'backstory': f"Has worked in {location} for years.",
            'dialogue': ["Hello there.", "What can I do for you?"]
        }
    
    def _generate_inventory(self, npc_type: str, char_class: str, level: int) -> List[Item]:
        """Rule-based inventory generation (no LLM call)"""
        items = []
        
        # Base items by NPC type
        if npc_type == 'merchant':
            items.append(Item("Healing Potion", "Restores health", "consumable", {"healing": "2d4+2"}, random.randint(2, 4)))
            items.append(Item("Torch", "Lights the way", "misc", {}, random.randint(3, 6)))
            items.append(Item("Rations", "A day's food", "consumable", {}, random.randint(5, 10)))
            if random.random() < 0.5:
                items.append(Item("Iron Dagger", "A simple blade", "weapon", {"damage": "1d4"}, 1))
            if random.random() < 0.3:
                items.append(Item("Leather Armor", "Basic protection", "armor", {"ac_bonus": 1}, 1))
        elif npc_type == 'guard':
            items.append(Item("Iron Sword", "Standard issue", "weapon", {"damage": "1d8"}, 1))
            items.append(Item("Chain Mail", "Guard armor", "armor", {"ac_bonus": 2}, 1))
            if random.random() < 0.4:
                items.append(Item("Healing Potion", "For emergencies", "consumable", {"healing": "2d4"}, 1))
        elif npc_type == 'wizard':
            items.append(Item("Wooden Staff", "Arcane focus", "weapon", {"damage": "1d6"}, 1))
            items.append(Item("Mana Potion", "Restores magic", "consumable", {"mana": "2d4"}, random.randint(1, 3)))
            if random.random() < 0.5:
                items.append(Item("Scroll of Light", "A minor spell", "consumable", {}, 1))
        else:  # commoner
            items.append(Item("Bread", "Simple food", "consumable", {}, random.randint(1, 3)))
            if random.random() < 0.3:
                items.append(Item("Knife", "A small blade", "weapon", {"damage": "1d4"}, 1))
            if random.random() < 0.2:
                items.append(Item("Lucky Charm", "Feels special", "misc", {}, 1))
        
        # Add class-specific item
        if char_class == 'cleric' and random.random() < 0.4:
            items.append(Item("Holy Symbol", "Divine focus", "misc", {}, 1))
        
        return items


async def create_npc_by_role(npc_name: str, location: str = "tavern",
                           recent_events: List[str] = None) -> NPCCharacter:
    """Convenience function to create NPC using the generator"""
    generator = NPCGenerator()
    return await generator.generate_npc(npc_name, location, recent_events)