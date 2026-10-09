import { DatabaseView } from "@/components/database-view";
import { Suspense } from "react";

export default function DatabasePage() {
  return (
    <Suspense fallback={<div className="page-frame py-16"><div className="panel p-8 text-sm text-slate-500">Loading database browser…</div></div>}>
      <DatabaseView />
    </Suspense>
  );
}
