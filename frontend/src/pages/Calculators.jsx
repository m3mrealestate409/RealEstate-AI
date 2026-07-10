import { useState } from "react";
import { api } from "../api/client.js";

// Deterministic calculators (Constitution §18). The UI only collects inputs and
// displays the backend-computed result — no math happens in the browser.
const CALCS = {
  emi: { label: "Home Loan EMI", fields: [
    { k: "principal", label: "Loan amount (₹)" },
    { k: "annual_rate", label: "Interest rate (% p.a.)" },
    { k: "tenure_months", label: "Tenure (months)" },
  ]},
  total_cost: { label: "Total Cost", fields: [
    { k: "base_price", label: "Base price" },
    { k: "area", label: "Area (sq ft)" },
    { k: "plc", label: "PLC (₹)" },
    { k: "gst_percent", label: "GST (%)" },
  ]},
  roi: { label: "ROI", fields: [
    { k: "investment", label: "Investment (₹)" },
    { k: "current_value", label: "Current value (₹)" },
    { k: "years", label: "Years (optional)" },
  ]},
  rental_yield: { label: "Rental Yield", fields: [
    { k: "annual_rent", label: "Annual rent (₹)" },
    { k: "property_value", label: "Property value (₹)" },
  ]},
  stamp_duty: { label: "Stamp Duty", fields: [
    { k: "property_value", label: "Property value (₹)" },
    { k: "rate", label: "Rate (%)" },
  ]},
};

export default function Calculators() {
  const [type, setType] = useState("emi");
  const [values, setValues] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const def = CALCS[type];

  function setField(k, v) {
    setValues((s) => ({ ...s, [k]: v }));
  }

  async function run(e) {
    e.preventDefault();
    setError("");
    setResult(null);
    const params = {};
    for (const f of def.fields) {
      if (values[f.k] !== undefined && values[f.k] !== "") params[f.k] = Number(values[f.k]);
    }
    try {
      const res = await api.calculate(type, params);
      setResult(res.result);
    } catch (err) {
      setError(err.message);
    }
  }

  function selectType(t) {
    setType(t);
    setValues({});
    setResult(null);
    setError("");
  }

  return (
    <div className="page">
      <div className="page-head">
        <h2>Calculators</h2>
        <p className="muted">All math runs on the backend — accurate and consistent every time.</p>
      </div>

      <div className="calc-tabs">
        {Object.entries(CALCS).map(([k, v]) => (
          <button key={k} className={`tab ${type === k ? "tab-active" : ""}`} onClick={() => selectType(k)}>
            {v.label}
          </button>
        ))}
      </div>

      <form className="calc-form" onSubmit={run}>
        <div className="calc-fields">
          {def.fields.map((f) => (
            <label className="field" key={f.k}>
              <span>{f.label}</span>
              <input type="number" step="any" value={values[f.k] ?? ""} onChange={(e) => setField(f.k, e.target.value)} />
            </label>
          ))}
        </div>
        <button className="btn btn-primary">Calculate</button>
      </form>

      {error && <div className="alert alert-error">{error}</div>}

      {result && (
        <div className="calc-result">
          <div className="block-title">Result</div>
          <table className="data-table">
            <tbody>
              {Object.entries(result).map(([k, v]) => (
                <tr key={k}>
                  <td className="result-key">{k.replace(/_/g, " ")}</td>
                  <td className="result-val">
                    {Array.isArray(v)
                      ? <NestedList rows={v} />
                      : typeof v === "number" ? v.toLocaleString("en-IN") : String(v)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function NestedList({ rows }) {
  return (
    <ul className="nested-list">
      {rows.map((r, i) => (
        <li key={i}>{Object.entries(r).map(([k, v]) => `${k}: ${typeof v === "number" ? v.toLocaleString("en-IN") : v}`).join(" · ")}</li>
      ))}
    </ul>
  );
}
