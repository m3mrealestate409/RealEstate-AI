// Source citation display (Constitution §9): Project, Source, Page, Last Updated, Confidence.

function confidenceClass(c) {
  if (c >= 0.85) return "conf-high";
  if (c >= 0.5) return "conf-mid";
  return "conf-low";
}

export function ConfidenceBadge({ value }) {
  const pct = Math.round((value || 0) * 100);
  return <span className={`conf-badge ${confidenceClass(value)}`}>Confidence {pct}%</span>;
}

export default function Citations({ citations }) {
  if (!citations || citations.length === 0) return null;
  return (
    <div className="citations">
      <div className="citations-title">Sources</div>
      <div className="citation-list">
        {citations.map((c, i) => (
          <div className="citation" key={i}>
            <span className="cite-project">{c.project || "—"}</span>
            <span className="cite-source">{c.source}</span>
            {c.page != null && <span className="cite-page">p.{c.page}</span>}
            {c.last_updated && (
              <span className="cite-updated">Updated {String(c.last_updated).slice(0, 10)}</span>
            )}
            {c.confidence != null && (
              <span className="cite-conf">{Math.round(c.confidence * 100)}%</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
