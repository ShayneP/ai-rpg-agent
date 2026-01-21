import { useEffect } from 'react';
import { useRoomContext } from '@livekit/components-react';
import { Room, RoomEvent, RpcInvocationData } from 'livekit-client';

type UpdateHandler = (update: any) => void | Promise<void>;

const subscribers = new Set<UpdateHandler>();
let registeredRoom: Room | null = null;

export function useGameStateUpdates(handler: UpdateHandler) {
  const room = useRoomContext();

  useEffect(() => {
    if (!room) return;

    const rpcHandler = async (data: RpcInvocationData): Promise<string> => {
      let update: any = null;
      try {
        const payload = typeof data.payload === 'string' ? data.payload : data.payload?.toString();
        update = payload ? JSON.parse(payload) : null;
      } catch (e) {
        console.error('[useGameStateUpdates] Failed to parse update payload', e);
        return JSON.stringify({ success: false, error: String(e) });
      }

      for (const h of Array.from(subscribers)) {
        try {
          await h(update);
        } catch (e) {
          console.error('[useGameStateUpdates] Handler error', e);
        }
      }

      return JSON.stringify({ success: true });
    };

    const ensureRegistered = (r: Room) => {
      if (registeredRoom === r) return;
      r.localParticipant.registerRpcMethod('game_state_update', rpcHandler);
      registeredRoom = r;
    };

    subscribers.add(handler);

    if (room.state === 'connected') {
      ensureRegistered(room);
    } else {
      const onConnected = () => {
        ensureRegistered(room);
        room.off(RoomEvent.Connected, onConnected);
      };
      room.on(RoomEvent.Connected, onConnected);
    }

    return () => {
      subscribers.delete(handler);
      if (subscribers.size === 0 && registeredRoom) {
        registeredRoom.localParticipant.unregisterRpcMethod('game_state_update');
        registeredRoom = null;
      }
    };
  }, [room, handler]);
}
