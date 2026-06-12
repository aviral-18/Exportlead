/**
 * Typed API client for BrassExport Intelligence backend.
 * All requests go to NEXT_PUBLIC_API_URL (default: http://localhost:8000)
 *
 * Every adapter function normalises the backend response into the shape the
 * TypeScript interfaces and components expect:
 *   - Unwraps nested envelope objects  (e.g. { deals: [...] } → [...])
 *   - Renames mismatched field names   (e.g. country_code → country)
 *   - Normalises pagination key        (results → items)
 */
import axios, { type AxiosInstance, type AxiosRequestConfig } from "axios";
import Cookies from "js-cookie";
import type {
  AuthTokens,
  Buyer,
  CountryHeatmapEntry,
  EmergingImporter,
  ExecutiveOverview,
  FollowUp,
  ForecastMonth,
  GrowthOpportunity,
  Lead,
  Opportunity,
  OutreachCampaign,
  PaginatedResponse,
  ProfitabilityInput,
  ProfitabilityResult,
  Recommendation,
} from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Axios client ──────────────────────────────────────────────────────────────

function createClient(): AxiosInstance {
  const client = axios.create({
    baseURL: `${BASE_URL}/api/v1`,
    headers: { "Content-Type": "application/json" },
    timeout: 30_000,
  });

  client.interceptors.request.use((config) => {
    const token = Cookies.get("access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  });

  client.interceptors.response.use(
    (res) => res,
    async (err) => {
      const original = err.config as AxiosRequestConfig & { _retry?: boolean };
      if (err.response?.status === 401 && !original._retry) {
        original._retry = true;
        const refreshToken = Cookies.get("refresh_token");
        if (refreshToken) {
          try {
            const { data } = await axios.post<AuthTokens>(
              `${BASE_URL}/api/v1/auth/refresh`,
              { refresh_token: refreshToken }
            );
            Cookies.set("access_token", data.access_token, { secure: true, sameSite: "strict" });
            Cookies.set("refresh_token", data.refresh_token, { secure: true, sameSite: "strict" });
            client.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
            return client(original);
          } catch {
            Cookies.remove("access_token");
            Cookies.remove("refresh_token");
            if (typeof window !== "undefined") window.location.href = "/login";
          }
        }
      }
      return Promise.reject(err);
    }
  );

  return client;
}

export const api = createClient();

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Normalise any backend paginated response (uses "results") to frontend shape (uses "items"). */
function normalisePage<T>(data: Record<string, unknown>, mapItem?: (item: Record<string, unknown>) => T): PaginatedResponse<T> {
  const raw = (data?.results ?? data?.items ?? []) as Record<string, unknown>[];
  const items = mapItem ? raw.map(mapItem) : (raw as unknown as T[]);
  const total = (data?.total as number) ?? items.length;
  const pageSize = (data?.page_size as number) ?? 50;
  return {
    items,
    total,
    page: (data?.page as number) ?? 1,
    page_size: pageSize,
    pages: Math.ceil(total / Math.max(1, pageSize)),
  };
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    api.post<AuthTokens>("/auth/login", { email, password }).then((r) => r.data),
  register: (email: string, password: string, full_name: string) =>
    api.post<AuthTokens>("/auth/register", { email, password, full_name }).then((r) => r.data),
  logout: (refresh_token: string) =>
    api.post("/auth/logout", { refresh_token }).then((r) => r.data),
  me: () => api.get("/auth/me").then((r) => r.data),
  googleLogin: () => api.get<{ url: string }>("/auth/google").then((r) => r.data),
};

// ── Executive dashboard ───────────────────────────────────────────────────────

export const executiveApi = {
  /** Flattens the deeply-nested /executive/overview into ExecutiveOverview. */
  overview: (): Promise<ExecutiveOverview> =>
    api.get("/executive/overview").then((r) => {
      const d = r.data as Record<string, Record<string, unknown>>;
      const bi = d?.buyer_intelligence ?? {};
      const crm = d?.crm_pipeline ?? {};
      const rev = d?.revenue ?? {};
      return {
        new_buyers_today: (bi.active_growth_opportunities as number) ?? 0,
        new_opportunities_today: (bi.active_growth_opportunities as number) ?? 0,
        active_leads: (crm.total_leads as number) ?? 0,
        active_deals: (crm.active_opportunities as number) ?? 0,
        total_pipeline_value_usd: (crm.pipeline_value_usd as number) ?? 0,
        expected_revenue_this_month_usd: (rev.confirmed_shipped_usd as number) ?? 0,
        top_country: "—",
        avg_deal_probability: 0,
        leads_by_status: {},
        buyers_by_tier: {
          emerging: (bi.emerging_importers as number) ?? 0,
          tier_a_b: (bi.tier_a_b_buyers as number) ?? 0,
        },
      };
    }),

  /** Extracts the deals array and normalises fields to match Opportunity. */
  activeDeals: (): Promise<Opportunity[]> =>
    api.get("/executive/active-deals").then((r) => {
      const deals = (r.data?.deals ?? []) as Record<string, unknown>[];
      return deals.map((d) => ({
        id: d.opportunity_id as number,
        lead_id: 0,
        title: (d.title as string) ?? "",
        stage: (d.stage as string) ?? "unknown",
        estimated_value_usd: (d.estimated_value_usd as number) ?? 0,
        probability_pct: (d.probability_pct as number) ?? 0,
        expected_close_date: d.expected_close_date as string | undefined,
        country: d.country_code as string | undefined,
        created_at: "",
        updated_at: "",
        closure_probability: d.probability_pct != null ? {
          probability_pct: d.probability_pct as number,
          confidence_level: (d.confidence_level as string) ?? "medium",
          days_to_close_est: d.days_to_close_est as number | undefined,
          expected_value_usd: d.estimated_value_usd as number ?? 0,
          weighted_value_usd: d.weighted_value_usd as number ?? 0,
          positive_signals: (d.positive_signals as string[]) ?? [],
          risk_factors: (d.risk_factors as string[]) ?? [],
        } : undefined,
      }));
    }),

  /** Extracts heatmap array and normalises field names. */
  countryHeatmap: (): Promise<CountryHeatmapEntry[]> =>
    api.get("/executive/country-heatmap").then((r) => {
      const heatmap = (r.data?.heatmap ?? []) as Record<string, unknown>[];
      return heatmap.map((h) => ({
        country: (h.country_code as string) ?? "",
        country_name: h.country_name as string | undefined,
        opportunity_index: (h.country_opportunity_index as number) ?? 0,
        active_leads: 0,
        pipeline_value_usd: (h.active_pipeline_usd as number) ?? 0,
        buyers_count: (h.buyer_count as number) ?? 0,
        top_tier_pct: (h.tier_a_b_buyers as number) ?? 0,
        avg_lead_score: (h.avg_lead_score as number) ?? 0,
      }));
    }),

  /** Extracts forecast array and renames keys to match ForecastMonth. */
  forecast: (): Promise<ForecastMonth[]> =>
    api.get("/executive/forecast").then((r) => {
      const forecast = (r.data?.forecast ?? []) as Record<string, unknown>[];
      return forecast.map((f) => ({
        month: (f.month as string) ?? "",
        base_usd: (f.base_case_usd as number) ?? 0,
        upside_usd: (f.upside_case_usd as number) ?? 0,
        downside_usd: (f.downside_case_usd as number) ?? 0,
        confirmed_usd: (f.confirmed_usd as number) ?? 0,
        pipeline_weighted_usd: (f.weighted_pipeline_usd as number) ?? 0,
      }));
    }),

  buyerHeatmap: () => api.get("/executive/buyer-heatmap").then((r) => r.data),

  /** Uses the growth recommendations endpoint (same data as growthApi.recommendations). */
  topOpportunities: (): Promise<Recommendation[]> =>
    api.get("/growth/recommendations").then((r) => {
      const recs = (r.data?.recommendations ?? []) as Record<string, unknown>[];
      return recs.map((rec) => ({
        rank: (rec.rank as number) ?? 0,
        opportunity_id: (rec.recommendation_id as number) ?? (rec.id as number) ?? 0,
        canonical_id: rec.canonical_id as number,
        opportunity_score: (rec.opportunity_score as number) ?? 0,
        company_name: (rec.company_name as string) ?? "",
        country: (rec.country_code as string) ?? (rec.country as string) ?? "",
        buyer_type: (rec.buyer_type as string) ?? "",
        annual_import_value_usd: (rec.estimated_value_usd as number) ?? 0,
        action_recommended: (rec.action_type as string) ?? "outreach",
        reasoning: (rec.reasoning as string) ?? "",
        is_emerging: (rec.is_emerging as boolean) ?? false,
        revenue_estimate_usd: (rec.revenue_estimate_usd as number) ?? (rec.estimated_value_usd as number) ?? 0,
        first_order_probability: (rec.first_order_probability as number) ?? 0,
      }));
    }),

  emergingImporters: (): Promise<EmergingImporter[]> =>
    api.get("/executive/emerging-importers").then((r) => {
      const importers = (r.data?.importers ?? []) as Record<string, unknown>[];
      return importers.map((em) => _normaliseEmergingImporter(em));
    }),

  pipelineAnalysis: () => api.get("/executive/pipeline-analysis").then((r) => r.data),
};

// ── Buyers ────────────────────────────────────────────────────────────────────

function _normaliseBuyer(raw: Record<string, unknown>): Buyer {
  const emails = (raw.email as string[]) ?? [];
  const products = (raw.product_categories as string[]) ?? [];
  return {
    id: raw.id as number,
    canonical_name: (raw.company_name as string) ?? "",
    country: (raw.country_code as string) ?? "",
    city: raw.city as string | undefined,
    buyer_type: (raw.buyer_type as string) ?? "",
    primary_product: products[0] ?? (raw.buyer_type as string) ?? "",
    annual_import_value_usd: (raw.estimated_annual_volume_usd as number) ?? 0,
    shipment_count: (raw.total_shipments as number) ?? 0,
    first_seen: (raw.first_import_date as string) ?? (raw.created_at as string) ?? "",
    last_seen: (raw.last_import_date as string) ?? (raw.updated_at as string) ?? "",
    website: raw.website as string | undefined,
    is_active: (raw.is_active as boolean) ?? true,
  };
}

export const buyersApi = {
  list: (params?: {
    page?: number;
    page_size?: number;
    country?: string;
    buyer_type?: string;
    min_score?: number;
    search?: string;
    sort?: string;
    order?: "asc" | "desc";
  }): Promise<PaginatedResponse<Buyer>> => {
    // Map frontend param names to backend param names
    const backendParams: Record<string, unknown> = {
      page: params?.page,
      page_size: params?.page_size,
      sort_by: params?.sort ?? "confidence_score",
      sort_order: params?.order ?? "desc",
    };
    if (params?.country) backendParams.country_code = params.country;
    if (params?.buyer_type) backendParams.buyer_type = params.buyer_type;
    if (params?.min_score) backendParams.min_confidence = params.min_score / 100;
    return api.get("/buyers/", { params: backendParams }).then((r) =>
      normalisePage<Buyer>(r.data as Record<string, unknown>, _normaliseBuyer)
    );
  },

  get: (id: number): Promise<Buyer> =>
    api.get(`/buyers/${id}`).then((r) => _normaliseBuyer(r.data as Record<string, unknown>)),

  search: (q: string, params?: Record<string, unknown>): Promise<PaginatedResponse<Buyer>> =>
    api.get("/search/buyers", { params: { q, ...params } }).then((r) =>
      normalisePage<Buyer>(r.data as Record<string, unknown>, _normaliseBuyer)
    ),
};

// ── Growth ────────────────────────────────────────────────────────────────────

function _normaliseGrowthOpportunity(raw: Record<string, unknown>): GrowthOpportunity {
  return {
    id: raw.id as number,
    canonical_id: raw.canonical_id as number,
    opportunity_score: (raw.opportunity_score as number) ?? 0,
    revenue_estimate_usd: (raw.estimated_value_usd as number) ?? 0,
    first_order_probability: (raw.india_import_probability as number) ?? 0,
    supplier_switch_probability: 0,
    country_opportunity_score: (raw.country_market_score as number) ?? 0,
    competitive_gap_score: (raw.competitive_gap_score as number) ?? 0,
    timing_score: (raw.market_timing_score as number) ?? 0,
    is_emerging_importer: (raw.is_emerging as boolean) ?? false,
    status: (raw.status as string) ?? "active",
    action_recommended: (raw.action_recommended as string) ?? "",
    reasoning: (raw.reasoning as string) ?? "",
    discovered_at: (raw.discovered_at as string) ?? "",
    buyer: {
      id: (raw.canonical_id as number) ?? 0,
      canonical_name: (raw.company_name as string) ?? `Buyer #${raw.canonical_id}`,
      country: (raw.country_code as string) ?? "",
      buyer_type: (raw.buyer_type as string) ?? "",
      city: raw.city as string | undefined,
      primary_product: "",
      annual_import_value_usd: 0,
      shipment_count: 0,
      first_seen: "",
      last_seen: (raw.last_import_date as string) ?? "",
      website: raw.website as string | undefined,
      is_active: true,
    },
  };
}

function _normaliseEmergingImporter(raw: Record<string, unknown>): EmergingImporter {
  return {
    id: raw.id as number,
    canonical_id: raw.canonical_id as number,
    months_active: (raw.months_active as number) ?? 0,
    shipment_count: (raw.shipment_count as number) ?? 0,
    annual_volume_usd: (raw.annual_volume_usd as number) ?? 0,
    growth_velocity_score: (raw.growth_velocity_score as number) ?? 0,
    overall_score: (raw.overall_score as number) ?? 0,
    category: (raw.category as string) ?? "",
    action_recommended: (raw.action_recommended as string) ?? "",
    detected_at: (raw.detected_at as string) ?? "",
    buyer: {
      id: (raw.canonical_id as number) ?? 0,
      canonical_name: (raw.company_name as string) ?? `Buyer #${raw.canonical_id}`,
      country: (raw.country_code as string) ?? "",
      buyer_type: (raw.buyer_type as string) ?? "",
      primary_product: "",
      annual_import_value_usd: raw.annual_volume_usd as number ?? 0,
      shipment_count: raw.shipment_count as number ?? 0,
      first_seen: "",
      last_seen: "",
      is_active: true,
    },
  };
}

export const growthApi = {
  /** Extracts .recommendations array and normalises country_code → country. */
  recommendations: (): Promise<Recommendation[]> =>
    api.get("/growth/recommendations").then((r) => {
      const recs = (r.data?.recommendations ?? []) as Record<string, unknown>[];
      return recs.map((rec) => ({
        rank: (rec.rank as number) ?? 0,
        opportunity_id: (rec.recommendation_id as number) ?? (rec.id as number) ?? 0,
        canonical_id: rec.canonical_id as number,
        opportunity_score: (rec.opportunity_score as number) ?? 0,
        company_name: (rec.company_name as string) ?? "",
        country: (rec.country_code as string) ?? (rec.country as string) ?? "",
        buyer_type: (rec.buyer_type as string) ?? "",
        annual_import_value_usd: (rec.estimated_value_usd as number) ?? 0,
        action_recommended: (rec.action_type as string) ?? "outreach",
        reasoning: (rec.reasoning as string) ?? "",
        is_emerging: (rec.is_emerging as boolean) ?? false,
        revenue_estimate_usd: (rec.revenue_estimate_usd as number) ?? (rec.estimated_value_usd as number) ?? 0,
        first_order_probability: (rec.first_order_probability as number) ?? 0,
      }));
    }),

  /** Normalises results→items and fixes GrowthOpportunity field names. */
  opportunities: (params?: {
    page?: number;
    page_size?: number;
    status?: string;
    country?: string;
    min_score?: number;
    emerging_only?: boolean;
  }): Promise<PaginatedResponse<GrowthOpportunity>> => {
    const backendParams: Record<string, unknown> = {
      page: params?.page,
      page_size: params?.page_size,
      status: params?.status ?? "active",
      min_score: params?.min_score,
    };
    if (params?.country) backendParams.country_code = params.country;
    if (params?.emerging_only) backendParams.is_emerging = true;
    return api.get("/growth/opportunities", { params: backendParams }).then((r) =>
      normalisePage<GrowthOpportunity>(
        r.data as Record<string, unknown>,
        _normaliseGrowthOpportunity
      )
    );
  },

  /** Normalises results→items for EmergingImporter. */
  emerging: (params?: { page?: number; page_size?: number }): Promise<PaginatedResponse<EmergingImporter>> =>
    api.get("/growth/emerging", { params }).then((r) =>
      normalisePage<EmergingImporter>(
        r.data as Record<string, unknown>,
        _normaliseEmergingImporter
      )
    ),

  updateOpportunityStatus: (id: number, status: string) =>
    api.patch(`/growth/opportunities/${id}/status`, { status }).then((r) => r.data),

  addToCrm: (id: number) =>
    api.post(`/growth/opportunities/${id}/add-to-crm`).then((r) => r.data),

  triggerDiscovery: () =>
    api.post("/growth/discovery/run").then((r) => r.data),
};

// ── CRM ───────────────────────────────────────────────────────────────────────

function _normaliseLead(raw: Record<string, unknown>): Lead {
  return {
    id: raw.id as number,
    canonical_id: raw.canonical_buyer_id as number | undefined,
    company_name: (raw.company_name as string) ?? "",
    country: (raw.country_code as string) ?? "",
    contact_name: raw.contact_name as string | undefined,
    email: raw.contact_email as string | undefined,
    phone: raw.contact_phone as string | undefined,
    status: (raw.status as Lead["status"]) ?? "new",
    source: (raw.source as string) ?? "database",
    estimated_value_usd: (raw.estimated_value_usd as number) ?? 0,
    notes: raw.notes as string | undefined,
    created_at: (raw.created_at as string) ?? "",
    last_contact_date: raw.last_contact_date as string | undefined,
    interactions_count: (raw.interactions_count as number) ?? 0,
  };
}

function _normaliseFollowUp(raw: Record<string, unknown>): FollowUp {
  return {
    id: raw.id as number,
    lead_id: raw.lead_id as number,
    title: (raw.title as string) ?? "",
    due_date: (raw.scheduled_at as string) ?? "",
    completed: (raw.is_completed as boolean) ?? false,
    priority: (raw.priority as FollowUp["priority"]) ?? "medium",
    notes: (raw.description as string) || (raw.outcome_notes as string) || undefined,
  };
}

export const crmApi = {
  leads: {
    list: (params?: {
      page?: number;
      page_size?: number;
      status?: string;
      country?: string;
      search?: string;
    }): Promise<PaginatedResponse<Lead>> => {
      const backendParams: Record<string, unknown> = {
        page: params?.page,
        page_size: params?.page_size,
        status: params?.status,
      };
      if (params?.country) backendParams.country_code = params.country;
      return api.get("/crm/leads/", { params: backendParams }).then((r) =>
        normalisePage<Lead>(r.data as Record<string, unknown>, _normaliseLead)
      );
    },
    get: (id: number): Promise<Lead> =>
      api.get(`/crm/leads/${id}`).then((r) => _normaliseLead(r.data as Record<string, unknown>)),
    create: (data: Partial<Lead>) =>
      api.post<Lead>("/crm/leads/", {
        company_name: data.company_name,
        country_code: data.country,
        contact_name: data.contact_name,
        contact_email: data.email,
        contact_phone: data.phone,
        status: data.status ?? "new",
        source: data.source ?? "database",
        estimated_value_usd: data.estimated_value_usd,
      }).then((r) => _normaliseLead(r.data as Record<string, unknown>)),
    update: (id: number, data: Partial<Lead>) =>
      api.patch<Lead>(`/crm/leads/${id}`, {
        status: data.status,
        contact_name: data.contact_name,
        contact_email: data.email,
        estimated_value_usd: data.estimated_value_usd,
      }).then((r) => _normaliseLead(r.data as Record<string, unknown>)),
  },
  opportunities: {
    list: (params?: { lead_id?: number; stage?: string }): Promise<Opportunity[]> =>
      api.get("/crm/opportunities/", { params }).then((r) => {
        const results = (r.data?.results ?? r.data?.items ?? []) as Record<string, unknown>[];
        return results.map((o) => ({
          id: o.id as number,
          lead_id: o.lead_id as number,
          title: (o.title as string) ?? "",
          stage: (o.stage as string) ?? "prospecting",
          estimated_value_usd: (o.estimated_value_usd as number) ?? 0,
          probability_pct: o.probability_pct as number | undefined,
          expected_close_date: o.expected_close_date as string | undefined,
          created_at: (o.created_at as string) ?? "",
          updated_at: (o.updated_at as string) ?? "",
        }));
      }),
    get: (id: number) =>
      api.get<Opportunity>(`/crm/opportunities/${id}`).then((r) => r.data),
    create: (data: Partial<Opportunity>) =>
      api.post<Opportunity>("/crm/opportunities/", data).then((r) => r.data),
    updateStage: (id: number, stage: string, notes?: string) =>
      api.patch(`/crm/opportunities/${id}`, { stage, notes }).then((r) => r.data),
  },
  followups: {
    /** Returns upcoming open follow-ups, normalised to FollowUp interface. */
    due: (_days_ahead?: number): Promise<FollowUp[]> =>
      api.get("/crm/followups/", { params: { is_completed: false, page_size: 50 } }).then((r) => {
        const results = (r.data?.results ?? r.data?.items ?? []) as Record<string, unknown>[];
        return results.map(_normaliseFollowUp);
      }),
    complete: (id: number) =>
      api.post(`/crm/followups/${id}/complete`).then((r) => r.data),
  },
  samples: {
    list: (lead_id?: number) =>
      api.get("/crm/samples/", { params: { lead_id } }).then((r) => r.data),
  },
  quotations: {
    list: (lead_id?: number) =>
      api.get("/crm/quotations/", { params: { lead_id } }).then((r) => r.data),
  },
};

// ── Profitability calculator ──────────────────────────────────────────────────

export const calculatorApi = {
  calculate: (input: ProfitabilityInput) =>
    api.post<ProfitabilityResult>("/calculator/calculate", input).then((r) => r.data),
  products: () =>
    api.get<string[]>("/calculator/products").then((r) => r.data),
  countries: () =>
    api.get<string[]>("/calculator/countries").then((r) => r.data),
};

// ── Outreach ──────────────────────────────────────────────────────────────────

export const outreachApi = {
  campaigns: {
    list: () => api.get<OutreachCampaign[]>("/outreach/campaigns").then((r) => r.data),
    create: (data: Partial<OutreachCampaign>) =>
      api.post<OutreachCampaign>("/outreach/campaigns", data).then((r) => r.data),
    launch: (id: number) =>
      api.post(`/outreach/campaigns/${id}/launch`).then((r) => r.data),
  },
  templates: () =>
    api.get<string[]>("/outreach/templates").then((r) => r.data),
  generateEmail: (template: string, buyer_id: number) =>
    api.post("/outreach/emails/generate", { template_name: template, buyer_id }).then((r) => r.data),
  replies: {
    list: (params?: { page?: number; sentiment?: string }) =>
      api.get("/outreach/replies", { params }).then((r) => r.data),
  },
  stats: () => api.get("/outreach/stats").then((r) => r.data),
};

// ── Analytics ─────────────────────────────────────────────────────────────────

export const analyticsApi = {
  overview: () => api.get("/analytics/overview").then((r) => r.data),

  trends: (metric: string, period?: string) =>
    api.get("/analytics/trends", { params: { metric, period } }).then((r) => r.data),

  /** Calls /analytics/by-country and normalises to { country, count, avg_score }. */
  countryTrends: () =>
    api.get("/analytics/by-country").then((r) => {
      const rows = Array.isArray(r.data) ? r.data : [];
      return (rows as Record<string, unknown>[]).map((c) => ({
        country: c.country_code as string,
        count: (c.buyer_count as number) ?? 0,
        avg_score: Math.round(((c.avg_confidence as number) ?? 0) * 100),
      }));
    }),

  productTrends: () => api.get("/analytics/by-buyer-type").then((r) => r.data),

  scoring: {
    /** Calls /scores/distribution — returns { total_scored, avg_score, by_tier }. */
    distribution: () => api.get("/scores/distribution").then((r) => r.data),

    /** Calls /scores/top and normalises to { name, score, country }[]. */
    topBuyers: (n?: number) =>
      api.get("/scores/top", { params: { limit: n ?? 10 } }).then((r) => {
        const results = (r.data?.results ?? []) as Record<string, unknown>[];
        return results.map((b) => ({
          name: (b.company_name as string) ?? "",
          score: ((b.score as Record<string, number>)?.composite_score) ?? 0,
          country: (b.country_code as string) ?? "",
        }));
      }),
  },
};
