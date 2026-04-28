export type ConsultationType =
  | 'legal'
  | 'financial'
  | 'Corporate & Business Services'
  | 'Employment & Human Resources'
  | 'Regulatory & Compliance'
  | 'Real Estate & Property'
  | 'Individuals & Personal Matters';

export const CONSULTATION_TYPES: readonly ConsultationType[] = [
  'legal',
  'financial',
  'Corporate & Business Services',
  'Employment & Human Resources',
  'Regulatory & Compliance',
  'Real Estate & Property',
  'Individuals & Personal Matters',
] as const;

export interface Consultation {
  id: number;
  consultation_type: ConsultationType;
  consultation_query: string;
  consultation_report: string;
  consultation_notes: string;
  created_at: string;
}

export interface ConsultationCreate {
  consultation_type: ConsultationType;
  consultation_query: string;
  consultation_report: string;
  consultation_notes: string;
}

export interface CaseReference {
  id: number;
  title: string;
  url: string;
  consultation_id: number | null;
  created_at: string;
}

export interface CaseReferenceCreate {
  title: string;
  url: string;
  consultation_id: number | null;
}

export interface HealthResponse {
  status: string;
}

export type ChatRole = 'system' | 'user' | 'assistant';

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface ChatRequest {
  messages: ChatMessage[];
  max_turns?: number | null;
}

export interface ChatResponse {
  message: string;
  model: string;
  evaluation_feedback?: string | null;
  evaluation_score?: number | null;
  final_report_summary?: string | null;
  final_report?: string | null;
}
