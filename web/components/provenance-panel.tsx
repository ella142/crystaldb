import type { Provenance } from "@/lib/types";
import { formatList, provenanceRows } from "@/lib/format";
import { LongValue } from "@/components/long-value";

function sourceFileItems(value: string): Array<{ name: string; fullPath: string }> {
  return value
    .split(";")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((fullPath) => {
      const name = fullPath.split(/[\\/]/).filter(Boolean).pop() || fullPath;
      return { name, fullPath };
    });
}

function SourceFilesValue({ value }: { value: string }) {
  const files = sourceFileItems(value);

  if (files.length === 0) {
    return <LongValue value={value} path />;
  }

  if (files.length === 1) {
    return (
      <span className="block truncate leading-6" title={files[0].fullPath}>
        {files[0].name}
      </span>
    );
  }

  return (
    <ul className="max-w-full space-y-1">
      {files.map((file) => (
        <li
          key={file.fullPath}
          className="truncate text-sm leading-6 text-ink"
          title={file.fullPath}
        >
          {file.name}
        </li>
      ))}
    </ul>
  );
}

export function ProvenancePanel({ provenance }: { provenance: Provenance }) {
  const rows = provenanceRows(provenance);
  const distinctEvidence =
    provenance.evidence && provenance.evidence !== provenance.source_file
      ? provenance.evidence
      : null;
  return (
    <section className="panel p-5">
      <div className="eyebrow">Provenance</div>
      <h2 className="mt-2 section-title">Source context preserved</h2>
      <dl className="mt-5 grid gap-4 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div
            key={label}
            className={`min-w-0 ${
              label === "Label method" || label === "Source file" ? "sm:col-span-2" : ""
            }`}
          >
            <dt className="data-label">{label}</dt>
            <dd className="data-value">
              {label === "Source file" ? (
                <SourceFilesValue value={value} />
              ) : (
                <LongValue
                  value={value}
                  path={label === "Source record"}
                  nowrap={label === "Label method"}
                />
              )}
            </dd>
          </div>
        ))}
      </dl>
      {distinctEvidence ? (
        <div className="mt-5 border-t border-line pt-4">
          <div className="data-label">Evidence</div>
          <div className="data-value">
            <LongValue value={distinctEvidence} path />
          </div>
        </div>
      ) : null}
      <div className="mt-5 border-t border-line pt-4">
        <div className="data-label">Notes</div>
        <div className="data-value">
          <LongValue value={formatList(provenance.notes)} />
        </div>
      </div>
    </section>
  );
}
