import Link from "next/link";

const principles = [
  ["Experimental XRD", "The measured profile is kept distinct from simulated or reconstructed diffraction."],
  ["Provenance-aware linkage", "Source identifiers, measurement context and structure relations remain visible together."],
  ["Candidate ambiguity", "Group-level candidates are shown as candidates; they are not silently collapsed into one answer."],
  ["Unresolved assignments", "Review states stay explicit when the available evidence does not resolve a structure."],
  ["Multi-phase measurements", "Mixtures are useful scientific records and remain visible as mixtures."],
  ["Reusable downloads", "When registered, scientific files can be retrieved in their source-oriented representation."],
];

export default function AboutPage() {
  return (
    <div className="page-frame py-12">
      <div className="max-w-3xl">
        <div className="eyebrow">Project scope</div>
        <h1 className="mt-3 page-title">About CrystalDB</h1>
        <p className="mt-4 text-base leading-7 text-slate-600">
          CrystalDB is a read-only research database interface for experimental diffraction measurements,
          crystallographic structure records and their provenance-aware relations.
        </p>
      </div>
      <div className="mt-10 grid gap-4 md:grid-cols-2">
        {principles.map(([title, body]) => (
          <section key={title} className="panel p-6">
            <h2 className="text-lg font-semibold text-ink">{title}</h2>
            <p className="mt-3 text-sm leading-6 text-slate-600">{body}</p>
          </section>
        ))}
      </div>
      <section className="mt-10 border-y border-line py-10">
        <h2 className="section-title">What CrystalDB does not claim</h2>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600">
          A mineral or material name is not automatically one unique crystal structure. A powder pattern
          is not automatically a proof of one CIF. CrystalDB does not infer missing wavelengths, assume Cu Kα,
          invent candidate probabilities or hide phase complexity for presentation convenience.
        </p>
        <Link href="/database" className="button-primary mt-6">Browse the live database</Link>
      </section>
    </div>
  );
}
