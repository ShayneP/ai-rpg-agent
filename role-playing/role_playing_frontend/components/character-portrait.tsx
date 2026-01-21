'use client';

import React, { useCallback, useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useRoomContext, useVoiceAssistant } from '@livekit/components-react';
import { cn } from '@/lib/utils';
import { useGameStateUpdates } from '@/hooks/useGameStateUpdates';

interface CharacterPortraitProps {
  className?: string;
}

export function CharacterPortrait({ className }: CharacterPortraitProps) {
  const room = useRoomContext();
  const { agent } = useVoiceAssistant();
  const [currentPortrait, setCurrentPortrait] = useState<string>('/portraits/narrator_card.png');
  const [characterName, setCharacterName] = useState<string>('Narrator');
  const [isVisible, setIsVisible] = useState(true);
  // Remove intervalRef as we're not using polling anymore

  // Debug log to see if component is mounting
  console.log('[CharacterPortrait] Component render, room:', room?.name, 'state:', room?.state);

  const updatePortraitFromContext = useCallback((context: any) => {
    console.log('[CharacterPortrait] Updating portrait from context:', JSON.stringify(context, null, 2));

    const agentPortraits: { [key: string]: { portrait: string; name: string } } = {
      narrator: { portrait: '/portraits/narrator_card.png', name: 'Narrator' },
      combat: { portrait: '/portraits/combat_card.png', name: 'Battle Mode' },
    };

    // Keywords to match against character names (order matters - more specific first)
    const npcPortraitKeywords: { keyword: string; portrait: string; name: string }[] = [
      { keyword: 'barkeep', portrait: '/portraits/barkeep_card.png', name: 'Barkeep' },
      { keyword: 'bartender', portrait: '/portraits/barkeep_card.png', name: 'Barkeep' },
      { keyword: 'innkeeper', portrait: '/portraits/barkeep_card.png', name: 'Innkeeper' },
      { keyword: 'goblin', portrait: '/portraits/goblin_card.png', name: 'Goblin' },
      { keyword: 'merchant', portrait: '/portraits/merchant_card.png', name: 'Merchant' },
      { keyword: 'shopkeeper', portrait: '/portraits/merchant_card.png', name: 'Merchant' },
      { keyword: 'vendor', portrait: '/portraits/merchant_card.png', name: 'Merchant' },
      { keyword: 'rogue', portrait: '/portraits/rogue_card.png', name: 'Rogue' },
      { keyword: 'thief', portrait: '/portraits/rogue_card.png', name: 'Rogue' },
    ];

    if (context.voice_acting_character) {
      const characterName = context.voice_acting_character.toLowerCase();

      // Find a matching portrait by keyword
      const match = npcPortraitKeywords.find(entry => characterName.includes(entry.keyword));

      if (match) {
        setCurrentPortrait((prev) => (prev !== match.portrait ? match.portrait : prev));
        setCharacterName(match.name);
      } else {
        setCurrentPortrait('/portraits/villager_card.png');
        // Use the original character name with proper capitalization
        const displayName = context.voice_acting_character
          .split(' ')
          .map((word: string) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
          .join(' ');
        setCharacterName(displayName);
      }
    } else {
      const portraitData = agentPortraits[context.agent_type] || agentPortraits['narrator'];
      setCurrentPortrait(portraitData.portrait);
      setCharacterName(portraitData.name);
    }
  }, []);

  const fetchCurrentContext = useCallback(async () => {
    if (!room || room.state !== 'connected' || !agent) return;
    try {
      const agentParticipant = agent;
      const response = await room.localParticipant.performRpc({
        destinationIdentity: agentParticipant.identity,
        method: 'get_current_context',
        payload: JSON.stringify({})
      });
      const data = typeof response === 'string' ? JSON.parse(response) : response;
      if (data.success && data.data) {
        updatePortraitFromContext(data.data);
      }
    } catch (error) {
      console.error('[CharacterPortrait] Failed to fetch context:', error);
    }
  }, [agent, room, updatePortraitFromContext]);

  useEffect(() => {
    if (!room || room.state !== 'connected' || !agent) return;
    fetchCurrentContext();
  }, [room?.state, agent, fetchCurrentContext]);

  useGameStateUpdates(async (update: any) => {
    if (!update) return;

    if (update.type === 'voice_acting_start' && update.data?.character_name) {
      // Use the character name directly from the event payload to avoid race conditions
      updatePortraitFromContext({
        voice_acting_character: update.data.character_name,
        agent_type: 'narrator'
      });
    } else if (update.type === 'voice_acting_end' || update.type === 'combat_start') {
      // Fetch context to get the correct agent type (could be narrator or combat)
      await fetchCurrentContext();
    }
  });

  return (
    <AnimatePresence mode="wait">
      {isVisible && (
        <motion.div
          key={currentPortrait}
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          className={cn(
            'relative overflow-hidden rounded-lg',
            'shadow-lg shadow-black/50',
            'aspect-[2/3]', // Fixed aspect ratio for portrait cards
            className
          )}
        >
          {/* Debug text if no image loads */}
          <div className="absolute inset-0 flex items-center justify-center bg-[#222222] text-white text-xs">
            {characterName}
          </div>
          
          {/* Portrait Image */}
          <img
            key={currentPortrait} // Force re-render when src changes
            src={currentPortrait}
            alt={characterName}
            className="h-full w-full object-cover relative z-10"
            onLoad={() => {
              console.log('[CharacterPortrait] Image loaded successfully:', currentPortrait);
            }}
            onError={(e) => {
              console.log('[CharacterPortrait] Image failed to load:', currentPortrait);
              // Fallback to narrator if image fails to load
              (e.target as HTMLImageElement).src = '/portraits/narrator_card.png';
            }}
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
