"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { calculatorApi } from "@/lib/api";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import { Calculator, TrendingUp, Package, Truck, FileText, ArrowRight, RefreshCw } from "lucide-react";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import type { ProfitabilityResult } from "@/types";

const FREIGHT_MODES = [
  { value: "sea", label: "Sea Freight" },
  { value: "air", label: "Air Freight" },
  { value: "express", label: "Express Courier" },
];

export function ProfitabilityDashboard() {
  const [form, setForm] = useState({
    product: "Brass Figurines",
    quantity: 1000,
    weight_kg: 100,
    destination_country: "AE",
    freight_mode: "sea" as "sea" | "air" | "express",
  });

  const { data: products } = useQuery({
    queryKey: ["calculator", "products"],
    queryFn: calculatorApi.products,
    staleTime: Infinity,
  });

  const { data: countries } = useQuery({
    queryKey: ["calculator", "countries"],
    queryFn: calculatorApi.countries,
    staleTime: Infinity,
  });

  const calc = useMutation({
    mutationFn: calculatorApi.calculate,
  });

  const result = calc.data as ProfitabilityResult | undefined;

  const costBreakdown = result
    ? [
        { name: "Product Cost", value: result.product_cost_usd, color: "#6366f1" },
        { name: "Freight", value: result.freight_usd, color: "#3b82f6" },
        { name: "Customs", value: result.customs_duty_usd, color: "#f59e0b" },
        { name: "Insurance", value: result.insurance_usd, color: "#10b981" },
        { name: "Bank/Other", value: result.bank_charges_usd + result.certification_usd, color: "#8b5cf6" },
      ].filter((d) => d.value > 0)
    : [];

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    calc.mutate(form);
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Profitability Calculator</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Full export cost breakdown with RoDTEP · IGST · drawback incentives
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        {/* Form */}
        <div className="lg:col-span-2">
          <form onSubmit={handleSubmit} className="rounded-xl border border-border bg-card p-5 space-y-4">
            <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <Calculator className="w-4 h-4 text-primary" />
              Export Parameters
            </h2>

            <div className="space-y-3">
              {/* Product */}
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1.5">Product</label>
                {products ? (
                  <select
                    value={form.product}
                    onChange={(e) => setForm((f) => ({ ...f, product: e.target.value }))}
                    className="w-full text-sm bg-background border border-border rounded-md px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    {products.map((p: string) => <option key={p} value={p}>{p}</option>)}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={form.product}
                    onChange={(e) => setForm((f) => ({ ...f, product: e.target.value }))}
                    className="w-full text-sm bg-background border border-border rounded-md px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-primary"
                    placeholder="e.g. Brass Figurines"
                  />
                )}
              </div>

              {/* Quantity */}
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1.5">Quantity (units)</label>
                <input
                  type="number"
                  min={1}
                  value={form.quantity}
                  onChange={(e) => setForm((f) => ({ ...f, quantity: Number(e.target.value) }))}
                  className="w-full text-sm bg-background border border-border rounded-md px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              {/* Weight */}
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1.5">Total Weight (kg)</label>
                <input
                  type="number"
                  min={0.1}
                  step={0.1}
                  value={form.weight_kg}
                  onChange={(e) => setForm((f) => ({ ...f, weight_kg: Number(e.target.value) }))}
                  className="w-full text-sm bg-background border border-border rounded-md px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              {/* Country */}
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1.5">Destination Country</label>
                {countries ? (
                  <select
                    value={form.destination_country}
                    onChange={(e) => setForm((f) => ({ ...f, destination_country: e.target.value }))}
                    className="w-full text-sm bg-background border border-border rounded-md px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    {countries.map((c: string) => <option key={c} value={c}>{c}</option>)}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={form.destination_country}
                    onChange={(e) => setForm((f) => ({ ...f, destination_country: e.target.value }))}
                    className="w-full text-sm bg-background border border-border rounded-md px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-primary"
                    placeholder="e.g. AE"
                  />
                )}
              </div>

              {/* Freight mode */}
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1.5">Freight Mode</label>
                <div className="grid grid-cols-3 gap-2">
                  {FREIGHT_MODES.map(({ value, label }) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, freight_mode: value as typeof form.freight_mode }))}
                      className={cn(
                        "py-2 text-xs rounded-md border transition-colors",
                        form.freight_mode === value
                          ? "bg-primary text-primary-foreground border-primary"
                          : "bg-background border-border text-foreground hover:bg-accent"
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={calc.isPending}
              className="w-full flex items-center justify-center gap-2 py-2.5 text-sm bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-70 font-medium"
            >
              {calc.isPending ? (
                <><RefreshCw className="w-4 h-4 animate-spin" /> Calculating...</>
              ) : (
                <><Calculator className="w-4 h-4" /> Calculate Profitability</>
              )}
            </button>
          </form>
        </div>

        {/* Results */}
        <div className="lg:col-span-3 space-y-4">
          {!result && !calc.isPending && (
            <div className="rounded-xl border border-dashed border-border bg-card/50 p-12 text-center">
              <Calculator className="w-10 h-10 mx-auto mb-3 text-muted-foreground opacity-40" />
              <p className="font-medium text-foreground">Ready to calculate</p>
              <p className="text-sm text-muted-foreground mt-1">Enter parameters and click Calculate</p>
            </div>
          )}

          {result && (
            <>
              {/* Summary cards */}
              <div className="grid grid-cols-2 gap-3">
                <div className={cn("rounded-xl p-4 border", result.net_margin_pct >= 20
                  ? "bg-emerald-50 border-emerald-200 dark:bg-emerald-900/10 dark:border-emerald-900"
                  : result.net_margin_pct >= 10
                  ? "bg-amber-50 border-amber-200 dark:bg-amber-900/10 dark:border-amber-900"
                  : "bg-red-50 border-red-200 dark:bg-red-900/10 dark:border-red-900"
                )}>
                  <p className="text-xs text-muted-foreground mb-1">Net Profit</p>
                  <p className="text-xl font-bold text-foreground">{formatCurrency(result.net_profit_usd)}</p>
                  <p className={cn("text-sm font-semibold mt-0.5",
                    result.net_margin_pct >= 20 ? "text-emerald-600" :
                    result.net_margin_pct >= 10 ? "text-amber-600" : "text-red-600"
                  )}>
                    {formatPercent(result.net_margin_pct)} net margin
                  </p>
                </div>

                <div className="rounded-xl p-4 border border-border bg-card">
                  <p className="text-xs text-muted-foreground mb-1">Total Export Cost</p>
                  <p className="text-xl font-bold text-foreground">{formatCurrency(result.total_export_cost_usd)}</p>
                  <p className="text-sm text-muted-foreground mt-0.5">
                    Incentives: <strong className="text-emerald-600">{formatCurrency(result.export_incentives_usd)}</strong>
                  </p>
                </div>
              </div>

              {/* Line items */}
              <div className="rounded-xl border border-border bg-card p-4">
                <h3 className="text-sm font-semibold text-foreground mb-3">Cost Breakdown</h3>
                <div className="space-y-2">
                  {[
                    { label: "Product Cost", value: result.product_cost_usd, icon: Package },
                    { label: "Packaging", value: result.packaging_usd, icon: Package },
                    { label: "Freight", value: result.freight_usd, icon: Truck },
                    { label: "Insurance", value: result.insurance_usd, icon: FileText },
                    { label: "Customs Duty", value: result.customs_duty_usd, icon: FileText },
                    { label: "Certification", value: result.certification_usd, icon: FileText },
                    { label: "Bank Charges", value: result.bank_charges_usd, icon: FileText },
                  ].map(({ label, value, icon: Icon }) => (
                    value > 0 ? (
                      <div key={label} className="flex items-center gap-3">
                        <Icon className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                        <span className="text-sm text-muted-foreground flex-1">{label}</span>
                        <span className="text-sm font-mono text-foreground">{formatCurrency(value)}</span>
                      </div>
                    ) : null
                  ))}
                  <div className="pt-2 border-t border-border flex items-center gap-3">
                    <ArrowRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                    <span className="text-sm font-semibold text-foreground flex-1">Export Incentives (RoDTEP + Drawback)</span>
                    <span className="text-sm font-mono font-semibold text-emerald-600">-{formatCurrency(result.export_incentives_usd)}</span>
                  </div>
                  <div className="pt-1 flex items-center gap-3">
                    <TrendingUp className="w-3.5 h-3.5 text-primary shrink-0" />
                    <span className="text-sm font-bold text-foreground flex-1">Selling Price</span>
                    <span className="text-sm font-mono font-bold text-primary">{formatCurrency(result.selling_price_usd)}</span>
                  </div>
                </div>
              </div>

              {/* Pie chart */}
              {costBreakdown.length > 0 && (
                <div className="rounded-xl border border-border bg-card p-4">
                  <h3 className="text-sm font-semibold text-foreground mb-3">Cost Distribution</h3>
                  <ResponsiveContainer width="100%" height={180}>
                    <PieChart>
                      <Pie
                        data={costBreakdown}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={80}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {costBreakdown.map((entry, index) => (
                          <Cell key={index} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(v: number) => formatCurrency(v)} />
                      <Legend wrapperStyle={{ fontSize: "11px" }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* INR note */}
              <p className="text-xs text-muted-foreground px-1">
                INR equivalent: approx. <strong className="text-foreground">
                  ₹{(result.inr_equivalent).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                </strong> (at ~84 INR/USD)
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
