import type { AppConfig } from './lib/types';

export const APP_CONFIG_DEFAULTS: AppConfig = {
  companyName: 'Dungeons & Agents — Inworld TTS 1.5 Max',
  pageTitle: 'Dungeons & Agents - AI Tabletop RPG',
  pageDescription: 'An AI-powered tabletop RPG adventure with Inworld voices',

  supportsChatInput: true,
  supportsVideoInput: true,
  supportsScreenShare: true,
  isPreConnectBufferEnabled: true,

  logo: '/lk-logo.svg',
  accent: '#398B5D',
  logoDark: '/lk-logo-dark.svg',
  accentDark: '#398B5D',
  startButtonText: 'Begin Your Adventure',
};
