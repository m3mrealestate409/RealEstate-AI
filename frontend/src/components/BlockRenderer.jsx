// Renders the structured answer blocks returned by /v1/query.
// Format priority mirrors Constitution §17: cards, tables, timeline, checklist, paragraph.

function fmt(v) {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") return v.toLocaleString("en-IN");
  return String(v);
}

function TableBlock({ block }) {
  return (
    <div className="block">
      <div className="block-title">{block.title}</div>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>{block.columns.map((c) => <th key={c}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {block.rows.map((row, i) => (
              <tr key={i}>{row.map((cell, j) => <td key={j}>{fmt(cell)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CardBlock({ block }) {
  return (
    <div className="block">
      <div className="block-title">{block.title}</div>
      <div className="card-grid">
        {block.cards.map((card, i) => (
          <div className="info-card" key={i}>
            <div className="info-card-head">{card.heading}</div>
            {card.subtitle && <div className="info-card-sub">{card.subtitle}</div>}
            <ul className="info-card-list">
              {(card.items || []).map((it, j) => <li key={j}>{it}</li>)}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

function TimelineBlock({ block }) {
  return (
    <div className="block">
      <div className="block-title">{block.title}</div>
      <div className="timeline">
        {block.events.map((e, i) => (
          <div className="timeline-item" key={i}>
            <div className="timeline-dot" />
            <div className="timeline-body">
              <div className="timeline-label">{e.label}</div>
              <div className="timeline-value">{fmt(e.value)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ChecklistBlock({ block }) {
  return (
    <div className="block">
      <div className="block-title">{block.title}</div>
      <ul className="checklist">
        {block.items.map((it, i) => (
          <li key={i}><span className="check">✓</span> {it}</li>
        ))}
      </ul>
    </div>
  );
}

function ParagraphBlock({ block }) {
  return (
    <div className="block">
      {block.title && <div className="block-title">{block.title}</div>}
      <p className="para">{block.text}</p>
    </div>
  );
}

export default function BlockRenderer({ block }) {
  switch (block.type) {
    case "table": return <TableBlock block={block} />;
    case "card": return <CardBlock block={block} />;
    case "timeline": return <TimelineBlock block={block} />;
    case "checklist": return <ChecklistBlock block={block} />;
    default: return <ParagraphBlock block={block} />;
  }
}
