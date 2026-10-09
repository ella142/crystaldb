import { labelLinkage, labelPhase } from "@/lib/format";

export function PhaseBadge({ value }: { value?: string | null }) {
  const tone =
    value === "multi_phase"
      ? "border-amber-100 bg-amber-50 text-amber-700"
      : value === "single_phase"
        ? "border-teal-100 bg-teal-50 text-teal-700"
        : "border-slate-200 bg-slate-50 text-slate-600";
  return <span className={`pill ${tone}`}>{labelPhase(value)}</span>;
}

export function LinkageBadge({ value }: { value?: string | null }) {
  const tone =
    value === "complete"
      ? "border-teal-100 bg-teal-50 text-teal-700"
      : value === "ambiguous"
        ? "border-amber-100 bg-amber-50 text-amber-700"
        : value === "partial"
          ? "border-blue-100 bg-blue-50 text-blue-700"
          : "border-slate-200 bg-slate-50 text-slate-600";
  return <span className={`pill ${tone}`}>{labelLinkage(value)}</span>;
}
