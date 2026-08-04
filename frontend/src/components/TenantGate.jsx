import { Link } from "react-router-dom";
import { getUser, useViewingOrg } from "../api/client.js";

// A super-admin manages several companies. Without a chosen company, the content
// tabs (Ask, Projects, Knowledge) would show every tenant's data mixed together
// — so we gate them: pick a company on the Platform page first. For a normal
// tenant user (always scoped to their own org) this is a transparent passthrough.
export default function TenantGate({ children }) {
  const viewing = useViewingOrg();
  const user = getUser();
  if (user?.is_super_admin && !viewing) {
    return (
      <div className="page">
        <div className="tenant-gate">
          <div className="tenant-gate-emoji">🏢</div>
          <h3>Pick a company to view its data</h3>
          <p className="muted">
            You manage more than one company. Open one from the Platform page to see just
            its Ask, Projects and Knowledge — instead of every tenant's data mixed together.
          </p>
          <Link className="btn btn-primary" to="/platform">Go to Platform →</Link>
        </div>
      </div>
    );
  }
  return children;
}
