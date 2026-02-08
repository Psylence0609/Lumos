export interface DeviceState {
  device_id: string;
  device_type: string;
  display_name: string;
  room: string;
  online: boolean;
  power: boolean;
  properties: Record<string, any>;
  current_watts: number;
  priority_tier: string;
  last_updated: string;
}

export interface RoomDevices {
  devices: DeviceState[];
}

export interface EnergyData {
  total_consumption_watts: number;
  solar_generation_watts: number;
  battery_pct: number;
  battery_mode: string;
  net_grid_watts: number;
}

export interface ThreatAssessment {
  threat_level: string;
  threat_type: string;
  urgency_score: number;
  summary: string;
  reasoning: string;
  recommended_actions: string[];
}

export interface AgentInfo {
  agent_id: string;
  display_name: string;
  status: string;
  last_action: string;
  last_reasoning: string;
  last_run: string | null;
  error: string | null;
}

export interface VoiceAlert {
  alert_id: string;
  message: string;
  audio_base64: string | null;
  require_permission: boolean;
  status: string;
}

export interface Pattern {
  pattern_id: string;
  type: string;
  name: string;
  description: string;
  frequency: number;
  confidence: number;
  approved: boolean;
  ready_to_suggest: boolean;
  actions: PatternAction[];
  last_occurrence: string;
}

export interface PatternAction {
  device_id: string;
  action: string;
  parameters: Record<string, any>;
  delay_seconds: number;
}

export interface Scenario {
  id: string;
  name: string;
  description: string;
  temporal?: boolean;
  total_steps?: number;
}

export interface ScenarioStep {
  scenario_id: string;
  current_step: number;
  total_steps: number;
  timestamp: string;
  title: string;
  description: string;
  metrics: Record<string, string>;
  is_last: boolean;
}

export interface SimulationStatus {
  time_multiplier: number;
  active_scenario: string | null;
  active_overrides: Record<string, any>;
  available_scenarios: Scenario[];
}

export interface SystemEvent {
  event_id: string;
  event_type: string;
  source: string;
  data: Record<string, any>;
  timestamp: string;
}

export interface WSMessage {
  type: string;
  data: any;
}
