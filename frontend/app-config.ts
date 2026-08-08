export interface AppConfig {
  pageTitle: string;
  pageDescription: string;
  companyName: string;

  supportsChatInput: boolean;
  supportsVideoInput: boolean;
  supportsScreenShare: boolean;
  isPreConnectBufferEnabled: boolean;

  logo: string;
  startButtonText: string;
  accent?: string;
  logoDark?: string;
  accentDark?: string;

  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  audioVisualizerColor?: `#${string}`;
  audioVisualizerColorDark?: `#${string}`;
  audioVisualizerColorShift?: number;
  audioVisualizerBarCount?: number;
  audioVisualizerGridRowCount?: number;
  audioVisualizerGridColumnCount?: number;
  audioVisualizerRadialBarCount?: number;
  audioVisualizerRadialRadius?: number;
  audioVisualizerWaveLineWidth?: number;

  // agent dispatch configuration
  agentName?: string;

  // LiveKit Cloud Sandbox configuration
  sandboxId?: string;
}

export const APP_CONFIG_DEFAULTS: AppConfig = {
  companyName: 'Farm & Field',
  pageTitle: 'Farm & Field Voice Assistant',
  pageDescription: 'Voice help for farmers — crop advice, weather, market   prices, and government schemes, in your language.',
  supportsChatInput: true,
  supportsVideoInput: false,
  supportsScreenShare: false,
  isPreConnectBufferEnabled: true,
  logo: '/farm-logo.svg',
  accent: '#2F5233',
  logoDark: '/farm-logo-dark.svg',
  accentDark: '#7BC96F',
  startButtonText: 'Talk to Your Farm Assistant',
  audioVisualizerType: 'bar',
  audioVisualizerColor: '#2F5233',
  audioVisualizerColorDark: '#7BC96F',
  audioVisualizerBarCount: 5,
  agentName: process.env.AGENT_NAME ?? undefined,
  sandboxId: undefined,
};