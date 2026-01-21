'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useRoomContext } from '@livekit/components-react';
import { cn } from '@/lib/utils';
import { useGameStateUpdates } from '@/hooks/useGameStateUpdates';

interface PlayerStats {
  name: string;
  class: string;
  level: number;
  current_health: number;
  max_health: number;
  ac: number;
  gold: number;
  stats: Record<string, number>;
}

interface InventoryItem {
  name: string;
  type: string;
  quantity: number;
  description: string;
  properties: Record<string, any>;
  is_equipped?: boolean;
}

interface CombatParticipant {
  name: string;
  type: 'player' | 'enemy';
  current_health: number;
  max_health: number;
  ac: number;
  is_current_turn: boolean;
}

interface GameState {
  game_state: string;
  player: PlayerStats | null;
  inventory: InventoryItem[];
  equipped: {
    weapon: string | null;
    armor: string | null;
  };
  story_state?: StoryState;
  side_quest_state?: SideQuestState;
}

interface CombatState {
  in_combat: boolean;
  combat: {
    round: number;
    current_turn_index: number;
    turn_order: string[];
    participants: CombatParticipant[];
  } | null;
}

interface SkillCheckResult {
  skill: string;
  difficulty: string;
  roll_total: number;
  dc: number;
  success: boolean;
  critical?: string | null;
  margin: number;
  description?: string;
  context_description?: string;
  timestamp?: number;
}

interface CombatCard {
  action: string;
  attacker: string;
  target: string;
  hit: boolean;
  damage: number;
  description: string;
  timestamp?: number;
  id?: string;
}

interface StoryObjective {
  id: string;
  description: string;
  type?: string;
  target?: string | null;
  completed: boolean;
}

interface StoryBeat {
  id: string;
  title: string;
  summary?: string;
  objectives?: StoryObjective[];
}

interface StoryState {
  active: StoryBeat[];
  completed: StoryBeat[];
  flags?: Record<string, boolean>;
}

interface SideQuestObjective {
  id: string;
  description: string;
  type: string;
  target: string;
  completed: boolean;
}

interface SideQuest {
  id: string;
  title: string;
  description: string;
  giver_name: string;
  giver_location: string;
  objectives: SideQuestObjective[];
  rewards: {
    gold?: number;
    xp?: number;
    item?: string;
  };
  status: 'active' | 'completed' | 'failed';
}

interface SideQuestState {
  active: SideQuest[];
  completed: string[];
  failed: string[];
}

export function GameStatus() {
  const room = useRoomContext();
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [combatState, setCombatState] = useState<CombatState | null>(null);
  const [showInventory, setShowInventory] = useState(false);
  const [skillCheck, setSkillCheck] = useState<SkillCheckResult | null>(null);
  const [combatCards, setCombatCards] = useState<CombatCard[]>([]);
  const [storyState, setStoryState] = useState<StoryState | null>(null);
  const [sideQuestState, setSideQuestState] = useState<SideQuestState | null>(null);
  const timeoutRef = React.useRef<NodeJS.Timeout | null>(null);

  const fetchGameState = useCallback(async () => {
    if (!room || room.state !== 'connected') return;
    try {
      const participants = Array.from(room.remoteParticipants.values());
      if (participants.length === 0) {
        console.warn('No remote participants found');
        return;
      }
      const agentParticipant = participants[0];
      const response = await room.localParticipant.performRpc({
        destinationIdentity: agentParticipant.identity,
        method: 'get_game_state',
        payload: ''
      });
      const data = JSON.parse(response);
      if (data.success) {
        setGameState(data.data);
        if (data.data.story_state) {
          setStoryState(data.data.story_state);
        }
        if (data.data.side_quest_state) {
          setSideQuestState(data.data.side_quest_state);
        }
      }
    } catch (error) {
      console.error('Failed to fetch game state:', error);
    }
  }, [room]);

  const fetchCombatState = useCallback(async () => {
    if (!room || room.state !== 'connected') return;
    try {
      const participants = Array.from(room.remoteParticipants.values());
      if (participants.length === 0) {
        console.warn('No remote participants found');
        return;
      }
      
      const agentParticipant = participants[0];
      
      const response = await room.localParticipant.performRpc({
        destinationIdentity: agentParticipant.identity,
        method: 'get_combat_state',
        payload: ''
      });
      const data = JSON.parse(response);
      if (data.success) {
        setCombatState(data.data);
      }
    } catch (error) {
      console.error('Failed to fetch combat state:', error);
    }
  }, [room]);

  useGameStateUpdates(async (update: any) => {
    if (!update) return;
    if (update.type === 'combat_action' || update.type === 'character_defeated') {
      await fetchCombatState();
      await fetchGameState();
    } else if (update.type === 'turn_started') {
      await fetchCombatState();
    } else if (update.type === 'inventory_changed') {
      await fetchGameState();
    } else if (update.type === 'skill_check') {
      const incoming: SkillCheckResult = {
        ...update.data,
        timestamp: Date.now(),
      };
      setSkillCheck(incoming);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setSkillCheck(null), 8000);
    } else if (update.type === 'combat_card') {
      const incoming: CombatCard = {
        ...update.data,
        id: `${Date.now()}-${Math.random()}`,
        timestamp: Date.now(),
      };
      setCombatCards((prev) => [...prev, incoming]);
      // Schedule removal of this card after 10s
      setTimeout(() => {
        setCombatCards((prev) => prev.filter((card) => card.id !== incoming.id));
      }, 10000);
      await fetchCombatState();
      await fetchGameState();
    } else if (update.type === 'story_update') {
      setStoryState(update.data);
      await fetchGameState();
    } else if (update.type === 'side_quest_update') {
      setSideQuestState(update.data);
      await fetchGameState();
    }
  });

  useEffect(() => {
    if (!room) return;

    const init = async () => {
      // Wait for room connection
      if (room.state !== 'connected') {
        await new Promise<void>((resolve) => {
          const check = () => {
            if (room.state === 'connected') resolve();
            else setTimeout(check, 100);
          };
          check();
        });
      }

      await fetchGameState();
      await fetchCombatState();
    };

    init();

    const interval = setInterval(() => {
      fetchGameState();
      fetchCombatState();
    }, 5000);

    return () => {
      clearInterval(interval);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [room, fetchCombatState, fetchGameState]);

  const renderSkillCheckCard = () => {
    if (!skillCheck) return null;
    
    const isCriticalSuccess = skillCheck.critical === 'nat20';
    const isCriticalFailure = skillCheck.critical === 'nat1';
    const hasCritical = isCriticalSuccess || isCriticalFailure;
    
    return (
      <motion.div
        key={skillCheck.timestamp}
        initial={{ opacity: 0, x: -60, scale: 0.95 }}
        animate={{ opacity: 1, x: 0, scale: 1 }}
        exit={{ opacity: 0, x: -60, scale: 0.95 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
        className={cn(
          'fixed top-20 left-4 z-40 w-80 overflow-hidden rounded-xl shadow-2xl',
          'border-2',
          skillCheck.success 
            ? 'border-emerald-400/70 bg-gradient-to-br from-emerald-900/95 via-emerald-950/95 to-green-950/95' 
            : 'border-rose-400/70 bg-gradient-to-br from-rose-900/95 via-rose-950/95 to-red-950/95'
        )}
      >
        {/* Header */}
        <div className={cn(
          'px-4 py-2 flex items-center justify-between',
          skillCheck.success ? 'bg-emerald-800/50' : 'bg-rose-800/50'
        )}>
          <div className="flex items-center gap-2">
            <span className="text-lg">🎲</span>
            <span className="text-xs font-bold uppercase tracking-widest text-white/80">
              Skill Check
            </span>
          </div>
          <div className={cn(
            'flex items-center gap-1.5 rounded-full px-2.5 py-1',
            skillCheck.success ? 'bg-emerald-500/30' : 'bg-rose-500/30'
          )}>
            <span className={cn(
              'text-xs font-bold uppercase tracking-wide',
              skillCheck.success ? 'text-emerald-200' : 'text-rose-200'
            )}>
              {skillCheck.success ? '✓ Success' : '✗ Failed'}
            </span>
          </div>
        </div>

        {/* Main Content */}
        <div className="p-4">
          {/* Skill Name & Difficulty */}
          <div className="flex items-baseline justify-between mb-4">
            <h3 className="text-xl font-bold text-white capitalize">
              {skillCheck.skill}
            </h3>
            <span className={cn(
              'text-xs font-semibold uppercase tracking-wide px-2 py-0.5 rounded',
              skillCheck.difficulty === 'easy' && 'bg-green-600/40 text-green-200',
              skillCheck.difficulty === 'medium' && 'bg-yellow-600/40 text-yellow-200',
              skillCheck.difficulty === 'hard' && 'bg-orange-600/40 text-orange-200',
              skillCheck.difficulty === 'very_hard' && 'bg-red-600/40 text-red-200',
              !['easy', 'medium', 'hard', 'very_hard'].includes(skillCheck.difficulty) && 'bg-gray-600/40 text-gray-200'
            )}>
              {skillCheck.difficulty.replace('_', ' ')}
            </span>
          </div>

          {/* Dice Roll Display */}
          <div className="grid grid-cols-3 gap-3 mb-4">
            {/* Roll */}
            <div className="bg-black/30 rounded-lg p-3 text-center border border-white/10">
              <p className="text-[10px] uppercase tracking-wider text-white/50 mb-1">Roll</p>
              <p className={cn(
                'text-2xl font-black tabular-nums',
                isCriticalSuccess && 'text-yellow-300 animate-pulse',
                isCriticalFailure && 'text-red-400',
                !hasCritical && 'text-white'
              )}>
                {skillCheck.roll_total}
              </p>
            </div>
            {/* vs */}
            <div className="flex items-center justify-center">
              <span className="text-white/40 text-sm font-medium">vs</span>
            </div>
            {/* DC */}
            <div className="bg-black/30 rounded-lg p-3 text-center border border-white/10">
              <p className="text-[10px] uppercase tracking-wider text-white/50 mb-1">DC</p>
              <p className="text-2xl font-black text-white tabular-nums">{skillCheck.dc}</p>
            </div>
          </div>

          {/* Margin */}
          <div className={cn(
            'flex items-center justify-center gap-2 py-2 px-3 rounded-lg mb-3',
            skillCheck.success ? 'bg-emerald-600/20' : 'bg-rose-600/20'
          )}>
            <span className="text-sm text-white/70">Margin:</span>
            <span className={cn(
              'text-lg font-bold tabular-nums',
              skillCheck.margin >= 0 ? 'text-emerald-300' : 'text-rose-300'
            )}>
              {skillCheck.margin >= 0 ? `+${skillCheck.margin}` : skillCheck.margin}
            </span>
          </div>

          {/* Critical Badge */}
          {hasCritical && (
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.2, type: 'spring', stiffness: 300 }}
              className={cn(
                'text-center py-2 px-3 rounded-lg mb-3 border',
                isCriticalSuccess 
                  ? 'bg-yellow-500/20 border-yellow-400/50' 
                  : 'bg-red-500/20 border-red-400/50'
              )}
            >
              <span className={cn(
                'text-sm font-bold uppercase tracking-wide',
                isCriticalSuccess ? 'text-yellow-200' : 'text-red-200'
              )}>
                {isCriticalSuccess ? '⭐ Natural 20 — Critical Success!' : '💀 Natural 1 — Critical Failure!'}
              </span>
            </motion.div>
          )}

          {/* Description */}
          {skillCheck.description && (
            <p className="text-sm text-white/80 leading-relaxed border-t border-white/10 pt-3 italic">
              "{skillCheck.description}"
            </p>
          )}
        </div>
      </motion.div>
    );
  };

  const getActionIcon = (action: string) => {
    const icons: Record<string, string> = {
      attack: '⚔️',
      defend: '🛡️',
      cast_spell: '✨',
      use_item: '🧪',
      flee: '🏃',
    };
    return icons[action] || '⚡';
  };

  const getActionColor = (action: string, hit: boolean) => {
    if (!hit && action === 'attack') {
      return {
        border: 'border-slate-500/60',
        bg: 'from-slate-800/95 via-slate-900/95 to-gray-900/95',
        header: 'bg-slate-700/50',
        accent: 'text-slate-300',
      };
    }
    const colors: Record<string, { border: string; bg: string; header: string; accent: string }> = {
      attack: {
        border: 'border-orange-500/60',
        bg: 'from-orange-900/95 via-red-950/95 to-rose-950/95',
        header: 'bg-orange-800/50',
        accent: 'text-orange-300',
      },
      defend: {
        border: 'border-sky-500/60',
        bg: 'from-sky-900/95 via-blue-950/95 to-indigo-950/95',
        header: 'bg-sky-800/50',
        accent: 'text-sky-300',
      },
      cast_spell: {
        border: 'border-violet-500/60',
        bg: 'from-violet-900/95 via-purple-950/95 to-fuchsia-950/95',
        header: 'bg-violet-800/50',
        accent: 'text-violet-300',
      },
      use_item: {
        border: 'border-emerald-500/60',
        bg: 'from-emerald-900/95 via-green-950/95 to-teal-950/95',
        header: 'bg-emerald-800/50',
        accent: 'text-emerald-300',
      },
      flee: {
        border: 'border-amber-500/60',
        bg: 'from-amber-900/95 via-yellow-950/95 to-orange-950/95',
        header: 'bg-amber-800/50',
        accent: 'text-amber-300',
      },
    };
    return colors[action] || colors.attack;
  };

  const renderCombatCards = () => {
    if (!combatCards.length) return null;
    return (
      <div className="fixed top-44 left-4 z-50 flex w-80 flex-col gap-3">
        <AnimatePresence>
          {combatCards.map((card) => {
            const colors = getActionColor(card.action, card.hit);
            const actionIcon = getActionIcon(card.action);
            
            return (
              <motion.div
                key={card.id}
                initial={{ opacity: 0, x: -60, scale: 0.95 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: -60, scale: 0.95 }}
                transition={{ duration: 0.3, ease: 'easeOut' }}
                className={cn(
                  'overflow-hidden rounded-xl shadow-2xl border-2',
                  colors.border,
                  `bg-gradient-to-br ${colors.bg}`
                )}
              >
                {/* Header */}
                <div className={cn('px-4 py-2 flex items-center justify-between', colors.header)}>
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{actionIcon}</span>
                    <span className="text-xs font-bold uppercase tracking-widest text-white/80">
                      {card.action.replace('_', ' ')}
                    </span>
                  </div>
                  {card.action === 'attack' && (
                    <div className={cn(
                      'flex items-center gap-1 rounded-full px-2.5 py-1',
                      card.hit ? 'bg-red-500/30' : 'bg-slate-500/30'
                    )}>
                      <span className={cn(
                        'text-xs font-bold uppercase tracking-wide',
                        card.hit ? 'text-red-200' : 'text-slate-300'
                      )}>
                        {card.hit ? '💥 Hit!' : '💨 Miss'}
                      </span>
                    </div>
                  )}
                </div>

                {/* Main Content */}
                <div className="p-4">
                  {/* Attacker → Target */}
                  <div className="flex items-center justify-center gap-3 mb-4">
                    <div className="flex-1 text-center">
                      <p className="text-[10px] uppercase tracking-wider text-white/50 mb-1">Attacker</p>
                      <p className="text-lg font-bold text-white truncate">{card.attacker}</p>
                    </div>
                    <div className="flex-shrink-0">
                      <motion.span
                        initial={{ x: -5 }}
                        animate={{ x: 5 }}
                        transition={{ repeat: Infinity, repeatType: 'reverse', duration: 0.6 }}
                        className={cn('text-2xl', colors.accent)}
                      >
                        →
                      </motion.span>
                    </div>
                    <div className="flex-1 text-center">
                      <p className="text-[10px] uppercase tracking-wider text-white/50 mb-1">Target</p>
                      <p className="text-lg font-bold text-white truncate">{card.target}</p>
                    </div>
                  </div>

                  {/* Damage Display (for attacks that hit) */}
                  {card.action === 'attack' && card.hit && typeof card.damage === 'number' && (
                    <motion.div
                      initial={{ scale: 0.8 }}
                      animate={{ scale: 1 }}
                      transition={{ type: 'spring', stiffness: 400, damping: 15 }}
                      className="bg-black/30 rounded-lg p-3 mb-3 border border-red-500/30"
                    >
                      <div className="flex items-center justify-center gap-3">
                        <span className="text-red-400 text-sm font-medium">Damage Dealt</span>
                        <span className="text-3xl font-black text-red-300 tabular-nums">
                          {card.damage}
                        </span>
                        <span className="text-red-400/60 text-xs uppercase">HP</span>
                      </div>
                    </motion.div>
                  )}

                  {/* Description */}
                  {card.description && (
                    <p className="text-sm text-white/75 leading-relaxed border-t border-white/10 pt-3">
                      {card.description}
                    </p>
                  )}
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    );
  };

  if (!gameState?.player) {
    return (
      <>
        <AnimatePresence>{renderSkillCheckCard()}</AnimatePresence>
        <AnimatePresence>{renderCombatCards()}</AnimatePresence>
      </>
    );
  }

  const healthPercentage = (gameState.player.current_health / gameState.player.max_health) * 100;
  const healthColor = healthPercentage > 50 ? 'bg-green-500' : healthPercentage > 25 ? 'bg-yellow-500' : 'bg-red-500';
  const activeBeats = storyState?.active ?? [];
  const completedBeats = storyState?.completed ?? [];

  return (
    <>
      <AnimatePresence>{renderSkillCheckCard()}</AnimatePresence>
      <AnimatePresence>{renderCombatCards()}</AnimatePresence>

      <div className="fixed top-20 right-4 bottom-4 w-80 space-y-4 z-40 overflow-y-auto pb-8 game-status-scroll">
      {/* Player Stats Card */}
      <motion.div
        initial={{ opacity: 0, x: 100 }}
        animate={{ opacity: 1, x: 0 }}
        className="bg-[#222222] backdrop-blur-sm rounded-lg p-4 border border-[#404040]"
      >
        <h3 className="text-lg font-bold text-white mb-2">
          {gameState.player.name} - Level {gameState.player.level} {gameState.player.class}
        </h3>

        {/* Health Bar */}
        <div className="mb-3">
          <div className="flex justify-between text-sm text-[#e0e0e0] mb-1">
            <span>Health</span>
            <span>{gameState.player.current_health} / {gameState.player.max_health}</span>
          </div>
          <div className="w-full bg-[#1a1a1a] rounded-full h-3 overflow-hidden">
            <motion.div
              className={cn('h-full', healthColor)}
              initial={{ width: 0 }}
              animate={{ width: `${healthPercentage}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="text-[#e0e0e0]">
            <span className="text-[#888888]">AC:</span> {gameState.player.ac}
          </div>
          <div className="text-[#e0e0e0]">
            <span className="text-[#888888]">Gold:</span> {gameState.player.gold}
          </div>
        </div>

        {/* Equipped Items */}
        {(gameState.equipped.weapon || gameState.equipped.armor) && (
          <div className="mt-3 pt-3 border-t border-[#404040] text-sm">
            {gameState.equipped.weapon && (
              <div className="text-[#e0e0e0]">
                <span className="text-[#888888]">Weapon:</span> {gameState.equipped.weapon}
              </div>
            )}
            {gameState.equipped.armor && (
              <div className="text-[#e0e0e0]">
                <span className="text-[#888888]">Armor:</span> {gameState.equipped.armor}
              </div>
            )}
          </div>
        )}
      </motion.div>

      {/* Combat Status */}
      <AnimatePresence>
        {combatState?.in_combat && combatState.combat && (
          <motion.div
            initial={{ opacity: 0, x: 100 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 100 }}
            className="bg-[#222222] backdrop-blur-sm rounded-lg p-4 border border-[#e05545]/50"
          >
            <h3 className="text-lg font-bold text-[#e05545] mb-2">Combat - Round {combatState.combat.round}</h3>

            <div className="space-y-2">
              {combatState.combat.participants.map((participant) => (
                <div
                  key={participant.name}
                  className={cn(
                    'p-2 rounded',
                    participant.is_current_turn ? 'bg-[#1a1a1a] ring-2 ring-[#398B5D]' : 'bg-[#1a1a1a]'
                  )}
                >
                  <div className="flex justify-between items-center">
                    <span className={cn(
                      'font-medium',
                      participant.type === 'player' ? 'text-[#398B5D]' : 'text-[#e05545]'
                    )}>
                      {participant.name}
                    </span>
                    <span className="text-sm text-[#e0e0e0]">
                      {participant.current_health}/{participant.max_health} HP
                    </span>
                  </div>
                  <div className="w-full bg-[#333333] rounded-full h-2 mt-1 overflow-hidden">
                    <div
                      className={participant.type === 'player' ? 'bg-[#398B5D]' : 'bg-[#e05545]'}
                      style={{ width: `${(participant.current_health / participant.max_health) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Quest Log */}
      <motion.div
        initial={{ opacity: 0, x: 100 }}
        animate={{ opacity: 1, x: 0 }}
        className="bg-[#222222] backdrop-blur-sm rounded-lg p-4 border border-[#404040]"
      >
        <h3 className="text-lg font-bold text-white mb-2">Quest Log</h3>
        {activeBeats.length === 0 ? (
          <p className="text-[#888888] text-sm">No active quests yet.</p>
        ) : (
          <div className="space-y-3">
            {activeBeats.map((beat) => (
              <div key={beat.id} className="rounded bg-[#1a1a1a] p-3">
                <p className="text-white text-sm font-semibold">{beat.title}</p>
                {beat.summary && (
                  <p className="text-[#b0b0b0] text-xs mt-1 leading-snug">{beat.summary}</p>
                )}
                {beat.objectives && beat.objectives.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {beat.objectives.map((obj) => (
                      <li key={obj.id} className="flex items-start gap-2 text-xs text-[#e0e0e0]">
                        <span
                          className={cn(
                            'mt-[2px] inline-block size-3 rounded-full border',
                            obj.completed
                              ? 'border-[#398B5D] bg-[#398B5D]'
                              : 'border-[#666666] bg-transparent'
                          )}
                        />
                        <span className={obj.completed ? 'text-[#4eca7a]' : 'text-[#e0e0e0]'}>
                          {obj.description || obj.id}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
        {completedBeats.length > 0 && (
          <div className="mt-3 border-t border-[#404040] pt-2">
            <p className="text-[#b0b0b0] text-xs uppercase tracking-wide mb-1">Completed</p>
            <ul className="space-y-1">
              {completedBeats.slice(0, 4).map((beat) => (
                <li key={beat.id} className="text-[#888888] text-xs">
                  {beat.title}
                </li>
              ))}
              {completedBeats.length > 4 && (
                <li className="text-[#666666] text-[11px]">+{completedBeats.length - 4} more</li>
              )}
            </ul>
          </div>
        )}
      </motion.div>

      {/* Side Quests */}
      {sideQuestState && sideQuestState.active.length > 0 && (
        <motion.div
          initial={{ opacity: 0, x: 100 }}
          animate={{ opacity: 1, x: 0 }}
          className="bg-[#222222] backdrop-blur-sm rounded-lg p-4 border border-[#398B5D]/50"
        >
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">📜</span>
            <h3 className="text-lg font-bold text-[#4eca7a]">Side Quests</h3>
            <span className="ml-auto text-xs text-[#398B5D] bg-[#1f3d2d] px-2 py-0.5 rounded-full">
              {sideQuestState.active.length} active
            </span>
          </div>
          <div className="space-y-3">
            {sideQuestState.active.map((quest) => (
              <div key={quest.id} className="rounded-lg bg-[#1a1a1a] p-3 border border-[#404040]">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-white text-sm font-semibold">{quest.title}</p>
                    <p className="text-[#888888] text-[10px] mt-0.5">
                      from {quest.giver_name} • {quest.giver_location.replace('_', ' ')}
                    </p>
                  </div>
                  {(quest.rewards.gold || quest.rewards.xp) && (
                    <div className="text-right text-[10px] text-[#e5a54a] shrink-0">
                      {quest.rewards.gold && <span>💰 {quest.rewards.gold}</span>}
                      {quest.rewards.gold && quest.rewards.xp && ' • '}
                      {quest.rewards.xp && <span>⭐ {quest.rewards.xp} XP</span>}
                    </div>
                  )}
                </div>
                <p className="text-[#b0b0b0] text-xs mt-2 leading-relaxed italic">
                  "{quest.description}"
                </p>
                {quest.objectives && quest.objectives.length > 0 && (
                  <ul className="mt-2 space-y-1.5 border-t border-[#404040] pt-2">
                    {quest.objectives.map((obj) => (
                      <li key={obj.id} className="flex items-start gap-2 text-xs">
                        <span
                          className={cn(
                            'mt-[3px] inline-block size-2.5 rounded-full border-2 shrink-0',
                            obj.completed
                              ? 'border-[#398B5D] bg-[#398B5D]'
                              : 'border-[#666666] bg-transparent'
                          )}
                        />
                        <span className={cn(
                          'leading-snug',
                          obj.completed ? 'text-[#4eca7a] line-through opacity-70' : 'text-[#e0e0e0]'
                        )}>
                          {obj.description}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
          {sideQuestState.completed.length > 0 && (
            <div className="mt-3 pt-2 border-t border-[#404040]">
              <p className="text-[#398B5D] text-[10px] uppercase tracking-wider">
                ✓ {sideQuestState.completed.length} completed
              </p>
            </div>
          )}
        </motion.div>
      )}

      {/* Inventory Toggle */}
      <motion.button
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        onClick={() => setShowInventory(!showInventory)}
        className="w-full bg-[#222222] backdrop-blur-sm rounded-lg p-3 border border-[#404040] text-white font-medium hover:bg-[#2a2a2a] transition-colors"
      >
        {showInventory ? 'Hide' : 'Show'} Inventory ({gameState.inventory.length} items)
      </motion.button>

      {/* Inventory */}
      <AnimatePresence>
        {showInventory && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="bg-[#222222] backdrop-blur-sm rounded-lg p-4 border border-[#404040] max-h-96 overflow-y-auto"
          >
            <h3 className="text-lg font-bold text-white mb-2">Inventory</h3>

            {gameState.inventory.length === 0 ? (
              <p className="text-[#888888] text-sm">Your inventory is empty</p>
            ) : (
              <div className="space-y-2">
                {gameState.inventory.map((item, index) => (
                  <div
                    key={`${item.name}-${index}`}
                    className={cn(
                      'p-2 rounded bg-[#1a1a1a] text-sm',
                      item.is_equipped && 'ring-2 ring-[#398B5D]'
                    )}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <span className="text-white font-medium">{item.name}</span>
                        {item.quantity > 1 && (
                          <span className="text-[#888888] ml-1">x{item.quantity}</span>
                        )}
                        {item.is_equipped && (
                          <span className="text-[#398B5D] text-xs ml-2">[Equipped]</span>
                        )}
                      </div>
                      <span className="text-[#888888] text-xs">{item.type}</span>
                    </div>
                    {item.description && (
                      <p className="text-[#888888] text-xs mt-1">{item.description}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
      </div>
    </>
  );
}
