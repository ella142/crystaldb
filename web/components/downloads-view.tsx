import Link from "next/link";

const formats = [
  ["Experimental powder XRD", "TXT and CSV", "Pattern XY endpoints serve the stored two_theta and intensity arrays without smoothing, resampling or silent normalization."],
  ["Structure records", "CIF", "The API serves registered source/canonical CIF files where a structure file is available."],
  ["Single-crystal reflection sets", "HKL", "Reflection-set endpoints serve registered HKL files and keep the reflection metadata separate."],
];

export function DownloadsView() {
  return (
    <div className="page-frame py-12">
      <div className="max-w-3xl">
        <div className="eyebrow">Scientific files</div>
        <h1 className="mt-3 page-title">Downloads</h1>
        <p className="mt-4 text-base leading-7 text-slate-600">
          CrystalDB exposes downloads only when the current API has a registered scientific file or
          data representation. Each file remains connected to the record and source identifiers shown in the UI.
        </p>
      </div>

      <div className="mt-10 grid gap-4">
        {formats.map(([title, fileType, description]) => (
          <div key={title} className="panel grid gap-5 p-6 sm:grid-cols-[220px_1fr_auto] sm:items-start">
            <div>
              <div className="eyebrow">{fileType}</div>
              <h2 className="mt-2 text-lg font-semibold text-ink">{title}</h2>
            </div>
            <p className="text-sm leading-6 text-slate-600">{description}</p>
            <Link href="/database" className="button-secondary whitespace-nowrap">Browse records</Link>
          </div>
        ))}
      </div>

      <section className="mt-10 rounded-lg border-l-2 border-blue-500 bg-blue-50/60 p-6">
        <div className="eyebrow">Current API boundary</div>
        <h2 className="mt-2 section-title">Bulk ZIP is available for selected records</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
          Select records in the database browser to choose all TXT, CIF, CSV, or complete data. Each
          selection is packaged with its manifest: one record uses manifest.json, while multiple records
          use one flat ZIP with manifest.csv at its root. Large exports should use a future backend
          streaming endpoint.
        </p>
      </section>

      <section className="mt-10 panel p-6">
        <div className="eyebrow">Using a record page</div>
        <h2 className="mt-2 section-title">Open Download on the record you need</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
          Pattern pages expose TXT and CSV when canonical XY data is registered. Structure pages expose CIF
          only when the API reports a registered file. Reflection pages follow the same rule for HKL.
          Missing files remain unavailable instead of producing empty downloads.
        </p>
      </section>
    </div>
  );
}
