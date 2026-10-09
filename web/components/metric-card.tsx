export function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="quiet-panel p-5">
      <div className="data-label">{label}</div>
      <div className="mt-2 text-3xl font-semibold text-ink">
        {value}
      </div>
      {detail ? <div className="mt-1 text-xs text-slate-500">{detail}</div> : null}
    </div>
  );
}
