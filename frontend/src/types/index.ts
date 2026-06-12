// ── Buyer / Lead scoring ──────────────────────────────────────────────────────

export interface Buyer {
  id: number;
  canonical_name: string;
  country: string;           // normalised from country_code
  city?: string;
  buyer_type: string;
  primary_product: string;
  annual_import_value_usd: number;
  shipment_count: number;
  first_seen: string;
  last_seen: string;
  website?: string;
  is_active: boolean;
  score?: LeadScore;
}

export interface LeadScore {
  id: number;
  canonical_id: number;
  composite_score: number;
  tier: "A" | "B" | "C" | "D" | "F";
  import_activity_score: number;
  product_fit_score: number;
  india_import_probability: number;
  growth_trend_score: number;
  supplier_switch_probability: number;
  new_importer_score: number;
  confidence: number;
  scored_at: string;
}

// ── CRM ───────────────────────────────────────────────────────────────────────

export type LeadStatus =
  | "new"
  | "contacted"
  | "engaged"
  | "qualified"
  | "sample_sent"
  | "quoted"
  | "negotiating"
  | "won"
  | "lost"
  | "inactive";

export interface Lead {
  id: number;
  canonical_id?: number;
  company_name: string;
  country: string;           // normalised from country_code
  contact_name?: string;
  email?: string;            // normalised from contact_email
  phone?: string;            // normalised from contact_phone
  status: LeadStatus;
  source: string;
  estimated_value_usd: number;
  notes?: string;
  created_at: string;
  last_contact_date?: string;
  interactions_count: number;
  buyer?: Buyer;
}

export interface Opportunity {
  id: number;
  lead_id: number;
  title: string;
  stage: string;
  estimated_value_usd: number;
  expected_close_date?: string;
  probability_pct?: number;
  country?: string;          // normalised from country_code in executive deals
  created_at: string;
  updated_at: string;
  lead?: Lead;
  closure_probability?: DealProbability;
}

export interface DealProbability {
  probability_pct: number;
  confidence_level: string;
  days_to_close_est?: number;
  expected_value_usd: number;
  weighted_value_usd: number;
  positive_signals: string[];
  risk_factors: string[];
}

export interface Contact {
  id: number;
  lead_id: number;
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
  job_title?: string;
  is_primary: boolean;
  created_at: string;
}

export interface Note {
  id: number;
  lead_id: number;
  content: string;
  note_type: string;
  created_at: string;
  created_by?: string;
}

export interface FollowUp {
  id: number;
  lead_id: number;
  title: string;
  due_date: string;          // normalised from scheduled_at
  completed: boolean;        // normalised from is_completed
  priority: "low" | "medium" | "high" | "urgent";
  notes?: string;            // normalised from description / outcome_notes
}

export interface Sample {
  id: number;
  lead_id: number;
  reference: string;
  product_name: string;
  status: string;
  sent_date?: string;
  feedback?: string;
  feedback_date?: string;
}

export interface Quotation {
  id: number;
  lead_id: number;
  reference: string;
  total_value_usd: number;
  status: string;
  valid_until?: string;
  created_at: string;
}

// ── Growth engine ─────────────────────────────────────────────────────────────

export interface GrowthOpportunity {
  id: number;
  canonical_id: number;
  opportunity_score: number;
  revenue_estimate_usd: number;    // normalised from estimated_value_usd
  first_order_probability: number; // normalised from india_import_probability
  supplier_switch_probability: number;
  country_opportunity_score: number;
  competitive_gap_score: number;
  timing_score: number;
  is_emerging_importer: boolean;   // normalised from is_emerging
  status: string;
  action_recommended: string;
  reasoning: string;
  discovered_at: string;
  buyer?: Buyer;                   // synthetic from company_name + country_code
}

export interface EmergingImporter {
  id: number;
  canonical_id: number;
  months_active: number;
  shipment_count: number;
  annual_volume_usd: number;
  growth_velocity_score: number;
  overall_score: number;
  category: string;
  action_recommended: string;
  detected_at: string;
  buyer?: Buyer;                   // synthetic from company_name + country_code
}

export interface Recommendation {
  rank: number;
  opportunity_id: number;
  canonical_id: number;
  opportunity_score: number;
  company_name: string;
  country: string;               // normalised from country_code
  buyer_type: string;
  annual_import_value_usd: number;
  action_recommended: string;
  reasoning: string;
  is_emerging: boolean;
  revenue_estimate_usd: number;
  first_order_probability: number;
}

// ── Executive dashboard ───────────────────────────────────────────────────────

export interface ExecutiveOverview {
  new_buyers_today: number;
  new_opportunities_today: number;
  active_leads: number;
  active_deals: number;
  total_pipeline_value_usd: number;
  expected_revenue_this_month_usd: number;
  top_country: string;
  avg_deal_probability: number;
  leads_by_status: Record<string, number>;
  buyers_by_tier: Record<string, number>;
}

export interface CountryHeatmapEntry {
  country: string;               // normalised from country_code
  country_name?: string;
  opportunity_index: number;     // normalised from country_opportunity_index
  active_leads: number;
  pipeline_value_usd: number;    // normalised from active_pipeline_usd
  buyers_count: number;          // normalised from buyer_count
  top_tier_pct: number;
  avg_lead_score?: number;
}

export interface ForecastMonth {
  month: string;
  base_usd: number;              // normalised from base_case_usd
  upside_usd: number;            // normalised from upside_case_usd
  downside_usd: number;          // normalised from downside_case_usd
  confirmed_usd: number;
  pipeline_weighted_usd: number; // normalised from weighted_pipeline_usd
}

export interface BuyerHeatmapEntry {
  buyer_type: string;
  tier: string;
  count: number;
  avg_score: number;
  total_import_value: number;
}

// ── Profitability calculator ──────────────────────────────────────────────────

export interface ProfitabilityInput {
  product: string;
  quantity: number;
  weight_kg: number;
  destination_country: string;
  freight_mode?: "air" | "sea" | "express";
  currency?: string;
}

export interface ProfitabilityResult {
  product: string;
  quantity: number;
  destination_country: string;
  product_cost_usd: number;
  packaging_usd: number;
  freight_usd: number;
  insurance_usd: number;
  customs_duty_usd: number;
  certification_usd: number;
  bank_charges_usd: number;
  total_export_cost_usd: number;
  export_incentives_usd: number;
  net_cost_usd: number;
  selling_price_usd: number;
  gross_profit_usd: number;
  gross_margin_pct: number;
  net_profit_usd: number;
  net_margin_pct: number;
  inr_equivalent: number;
}

// ── Outreach ──────────────────────────────────────────────────────────────────

export interface OutreachCampaign {
  id: number;
  name: string;
  template_name: string;
  status: string;
  emails_sent: number;
  emails_opened: number;
  replies_received: number;
  positive_replies: number;
  created_at: string;
  launched_at?: string;
}

export interface EmailReply {
  id: number;
  from_email: string;
  subject: string;
  body_text: string;
  sentiment: string;
  intent: string;
  confidence_score: number;
  suggested_action: string;
  received_at: string;
}

// ── Pagination ────────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "manager" | "analyst" | "viewer";
  avatar_url?: string;
  is_verified: boolean;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

// ── WebSocket events ──────────────────────────────────────────────────────────

export interface WsEvent<T = unknown> {
  event: string;
  data: T;
  ts: string;
}
