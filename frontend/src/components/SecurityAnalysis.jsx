
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import "./SecurityAnalysis.css";

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"];
const MAX_QUERY_LENGTH = 10000;
const MAX_TABLE_NAMES = 200;

function unwrapConnections(response) {
  if (Array.isArray(response)) return response;
  if (Array.isArray(response?.connections)) return response.connections;
  if (Array.isArray(response?.data?.connections)) {
    return response.data.connections;
  }
  if (Array.isArray(response?.data)) return response.data;
  return [];
}

function unwrapResponse(response) {
  let data = response?.data ?? response;

  // Support an additional API response wrapper without
  // assuming that every response has the same nesting.
  if (
    data?.data &&
    typeof data.data === "object" &&
    !Array.isArray(data.data)
  ) {
    data = data.data;
  }

  return data && typeof data === "object" ? data : {};
}

function formatLabel(value) {
  if (value === null || value === undefined || value === "") {
    return "Unknown";
  }

  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function normalizeSeverity(value) {
  const severity = String(value || "info").toLowerCase();

  return SEVERITY_ORDER.includes(severity) ? severity : "info";
}

function getSeverityCount(counts, severity) {
  const value = Number(counts?.[severity] ?? 0);

  return Number.isFinite(value) && value >= 0 ? value : 0;
}

function SecurityAnalysis() {
  const [connections, setConnections] = useState([]);
  const [selectedConnection, setSelectedConnection] = useState("");
  const [query, setQuery] = useState("");
  const [tableNamesInput, setTableNamesInput] = useState("");
  const [result, setResult] = useState(null);

  const [loadingConnections, setLoadingConnections] = useState(true);
  const [scanning, setScanning] = useState(false);

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadConnections = useCallback(async () => {
    setLoadingConnections(true);
    setError("");

    try {
      const response = await api.getConnections();
      const items = unwrapConnections(response);

      setConnections(items);

      setSelectedConnection((current) => {
        if (
          current &&
          items.some(
            (item) =>
              String(item.connection_id) === String(current)
          )
        ) {
          return current;
        }

        return items.length
          ? String(items[0].connection_id)
          : "";
      });
    } catch (requestError) {
      setConnections([]);
      setSelectedConnection("");
      setError(
        requestError.message ||
          "Unable to load database connections."
      );
    } finally {
      setLoadingConnections(false);
    }
  }, []);

  useEffect(() => {
    loadConnections();
  }, [loadConnections]);

  const data = useMemo(
    () => unwrapResponse(result),
    [result]
  );

  const findings = useMemo(
    () => (Array.isArray(data.findings) ? data.findings : []),
    [data]
  );

  const severityCounts = data.severity_counts || {};
  const databaseScan = data.database_scan || {};

  const sortedFindings = useMemo(() => {
    return [...findings].sort((a, b) => {
      const severityA = normalizeSeverity(a.severity);
      const severityB = normalizeSeverity(b.severity);

      return (
        SEVERITY_ORDER.indexOf(severityA) -
        SEVERITY_ORDER.indexOf(severityB)
      );
    });
  }, [findings]);

  async function handleScan(event) {
    event.preventDefault();

    setError("");
    setNotice("");

    if (!selectedConnection) {
      setError(
        "Add and select a database connection before running a security scan."
      );
      return;
    }

    if (query.length > MAX_QUERY_LENGTH) {
      setError(
        `SQL query must not exceed ${MAX_QUERY_LENGTH.toLocaleString()} characters.`
      );
      return;
    }

    const tableNames = [
      ...new Set(
        tableNamesInput
          .split(",")
          .map((name) => name.trim())
          .filter(Boolean)
      ),
    ];

    if (tableNames.length > MAX_TABLE_NAMES) {
      setError(
        `You can specify at most ${MAX_TABLE_NAMES} table names.`
      );
      return;
    }

    const invalidNames = tableNames.filter(
      (name) => !/^[A-Za-z0-9_$]+$/.test(name)
    );

    if (invalidNames.length > 0) {
      setError(
        "Table names can contain only letters, numbers, underscores, and dollar signs."
      );
      return;
    }

    try {
      setScanning(true);

      const response = await api.analyzeSecurity({
        connectionId: Number(selectedConnection),
        query,
        tableNames,
      });

      const responseData = unwrapResponse(response);

      if (!Array.isArray(responseData.findings)) {
        throw new Error(
          "The security analysis response did not contain a valid findings list."
        );
      }

      setResult(response);

      setNotice(
        response.message ||
          "Database security analysis completed."
      );
    } catch (requestError) {
      // Keep the previous successful results visible if
      // a later scan fails.
      setError(
        requestError.message || "Security analysis failed."
      );
    } finally {
      setScanning(false);
    }
  }

  function clearForm() {
    setQuery("");
    setTableNamesInput("");
    setResult(null);
    setError("");
    setNotice("");
  }

  return (
    <main className="security-page">
      <header className="security-page-header">
        <div>
          <h2>Database Security Analysis</h2>
          <p>
            Review SQL security heuristics, MySQL privileges,
            and potentially sensitive schema columns.
          </p>
        </div>

        <button
          type="button"
          className="security-refresh-button"
          onClick={loadConnections}
          disabled={loadingConnections || scanning}
        >
          {loadingConnections
            ? "Loading..."
            : "↻ Refresh connections"}
        </button>
      </header>

      {error && (
        <div className="security-alert error" role="alert">
          {error}
        </div>
      )}

      {notice && (
        <div className="security-alert success" role="status">
          {notice}
        </div>
      )}

      <section className="security-panel">
        <div className="security-panel-heading">
          <div>
            <h3>Run a security scan</h3>
            <p>
              Scans metadata and visible grants for the selected
              database connection.
            </p>
          </div>

          <span className="security-readonly-badge">
            METADATA-ONLY SCAN
          </span>
        </div>

        <form onSubmit={handleScan}>
          <label className="security-field">
            Database connection

            <select
              value={selectedConnection}
              onChange={(event) => {
                setSelectedConnection(event.target.value);
                setError("");
                setNotice("");
              }}
              disabled={
                loadingConnections || connections.length === 0
              }
            >
              {connections.length === 0 && (
                <option value="">No saved connections</option>
              )}

              {connections.map((connection) => (
                <option
                  key={connection.connection_id}
                  value={connection.connection_id}
                >
                  {connection.connection_name} —{" "}
                  {connection.database_name}
                </option>
              ))}
            </select>
          </label>

          <label className="security-field">
            SQL query to inspect{" "}
            <span className="security-optional">
              (optional)
            </span>

            <textarea
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setError("");
              }}
              rows={6}
              maxLength={MAX_QUERY_LENGTH}
              spellCheck="false"
              placeholder="Paste a SQL statement for heuristic security analysis. The submitted query is analyzed, not executed."
            />

            <small>
              {query.length.toLocaleString()} /{" "}
              {MAX_QUERY_LENGTH.toLocaleString()} characters
            </small>
          </label>

          <label className="security-field">
            Tables to scan{" "}
            <span className="security-optional">
              (optional, comma-separated)
            </span>

            <input
              type="text"
              value={tableNamesInput}
              onChange={(event) => {
                setTableNamesInput(event.target.value);
                setError("");
              }}
              placeholder="employees, accounts, customers"
            />

            <small>
              Leave blank to scan the selected schema, subject
              to the backend's 5,000-column limit.
            </small>
          </label>

          <div className="security-form-footer">
            <span>
              Only schema metadata and grants are inspected;
              table row values are not read.
            </span>

            <div className="security-actions">
              <button
                type="button"
                className="security-secondary-button"
                onClick={clearForm}
                disabled={scanning}
              >
                Clear
              </button>

              <button
                type="submit"
                className="security-primary-button"
                disabled={
                  scanning ||
                  loadingConnections ||
                  !connections.length
                }
              >
                {scanning
                  ? "Scanning database..."
                  : "Run Security Analysis"}
              </button>
            </div>
          </div>
        </form>

        {!loadingConnections && connections.length === 0 && (
          <div className="security-empty-inline">
            No saved database connections. Add a MySQL connection
            before running the scan.
          </div>
        )}
      </section>

      {!result && (
        <section className="security-empty-state">
          <div className="security-empty-icon">⬡</div>

          <h3>Security findings will appear here</h3>

          <p>
            Choose a database connection and optionally provide
            a SQL query or table list to begin.
          </p>
        </section>
      )}

      {result && (
        <div className="security-results">
          <section className="security-panel">
            <div className="security-panel-heading">
              <div>
                <h3>Security scan overview</h3>
                <p>
                  Findings are heuristic indicators and should
                  be reviewed in context.
                </p>
              </div>

              <span className="security-saved-count">
                {Number(data.saved_findings_count || 0)} saved
              </span>
            </div>

            <div className="security-summary-grid">
              <div className="security-summary-card total">
                <span>Total findings</span>
                <strong>
                  {Number(
                    data.findings_count ?? findings.length
                  )}
                </strong>
              </div>

              {SEVERITY_ORDER.map((severity) => (
                <div
                  className={`security-summary-card ${severity}`}
                  key={severity}
                >
                  <span>{formatLabel(severity)}</span>
                  <strong>
                    {getSeverityCount(severityCounts, severity)}
                  </strong>
                </div>
              ))}
            </div>

            <div className="security-scan-stats">
              <div>
                <span>Columns examined</span>
                <strong>
                  {Number(
                    databaseScan.columns_examined || 0
                  ).toLocaleString()}
                </strong>
              </div>

              <div>
                <span>Privilege grants reviewed</span>
                <strong>
                  {Number(
                    databaseScan.privilege_grants_reviewed || 0
                  ).toLocaleString()}
                </strong>
              </div>

              <div>
                <span>Connection ID</span>
                <strong>
                  {formatLabel(data.connection_id)}
                </strong>
              </div>
            </div>

            {databaseScan.sensitive_data_scan_reads_row_values ===
              false && (
              <p className="security-privacy-note">
                <strong>Privacy:</strong> The sensitive-column
                scan used metadata only. No table row values were read.
              </p>
            )}
          </section>

          <section className="security-panel">
            <div className="security-panel-heading">
              <div>
                <h3>Security findings</h3>
                <p>
                  {sortedFindings.length} finding(s), ordered
                  by severity.
                </p>
              </div>
            </div>

            {sortedFindings.length > 0 ? (
              <div className="security-findings-list">
                {sortedFindings.map((finding, index) => {
                  const severity = normalizeSeverity(
                    finding.severity
                  );

                  return (
                    <article
                      className="security-finding-card"
                      key={
                        finding.finding_id ??
                        `${finding.finding_type}-${finding.title}-${index}`
                      }
                    >
                      <div className="security-finding-top">
                        <div>
                          <span className="security-finding-type">
                            {formatLabel(finding.finding_type)}
                          </span>

                          <h4>
                            {finding.title || "Security finding"}
                          </h4>
                        </div>

                        <span
                          className={`security-severity ${severity}`}
                        >
                          {severity}
                        </span>
                      </div>

                      <p className="security-finding-description">
                        {finding.description ||
                          "No additional description provided."}
                      </p>

                      {finding.affected_object && (
                        <div className="security-affected-object">
                          <span>Affected object</span>
                          <code>{finding.affected_object}</code>
                        </div>
                      )}

                      {finding.recommendation && (
                        <div className="security-recommendation">
                          <strong>Recommendation</strong>
                          <p>{finding.recommendation}</p>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className="security-no-findings">
                No findings were returned by this scan.
                This does not prove that the database or SQL
                is fully secure.
              </div>
            )}
          </section>

          {Array.isArray(data.limitations) &&
            data.limitations.length > 0 && (
              <section className="security-panel">
                <div className="security-panel-heading">
                  <div>
                    <h3>Analysis limitations</h3>
                    <p>
                      Important context for interpreting this scan.
                    </p>
                  </div>
                </div>

                <ul className="security-limitations">
                  {data.limitations.map((limitation, index) => (
                    <li key={index}>{limitation}</li>
                  ))}
                </ul>
              </section>
            )}
        </div>
      )}
    </main>
  );
}

export default SecurityAnalysis;