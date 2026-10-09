export function EmptyState({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-lg border border-dashed border-line bg-white px-6 py-10 text-center">
      <div className="text-base font-semibold text-ink">{title}</div>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-500">{body}</p>
    </div>
  );
}

export function ApiUnavailable() {
  return (
    <EmptyState
      title="CrystalDB API is currently unavailable."
      body="Start the FastAPI service and reload this page. The interface does not substitute development fixtures for scientific records."
    />
  );
}
