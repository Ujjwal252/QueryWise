
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import "./ExecutionPlans.css";

const DEFAULT_QUERY = `SELECT employee_id, employee_name
FROM employees
WHERE department = 'Engineering';`;

const MAX_QUERY_LENGTH = 10000;

function getConnectionList(response) {
  if (Array.isArray(response)) return response;
  if (Array.isArray(response?.connections)) return response.connections;
  if (Array.isArray(response?.data?.connections)) {
    return response.data.connections;
  }
  if (Array.isArray(response?.data)) return response.data;
  return [];
}

function getResponseData(response) {
  return response?.data?.data ?? response?.data ?? response;
}

function getPlanObject(response) {
  const data = getResponseData(response);

  return (
    data?.execution_plan ??
    data?.plan ??
    response?.execution_plan ??
    response?.plan ??
    null
  );
}

function getAnalysisObject(response) {
  const data = getResponseData(response);

  return (
    data?.analysis ??
    data?.execution_analysis ??
    response?.analysis ??
    response?.execution_analysis ??
    null
  );
}

function getIndexObject(response) {
  const data = getResponseData(response);

  return (
    data?.index_analysis ??
    response?.index_analysis ??
    null
  );
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  if (Array.isArray(value)) {
    return value.length ? value.join(", ") : "None";
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}

function findEstimatedQueryCost(node) {
  if (!node || typeof node !== "object") return null;

  if (Array.isArray(node)) {
    for (const item of node) {
      const cost = findEstimatedQueryCost(item);
      if (cost !== null && cost !== undefined) return cost;
    }
    return null;
  }

  if (node.cost_info?.query_cost !== undefined) {
    return node.cost_info.query_cost;
  }

  if (node.query_cost !== undefined) {
    return node.query_cost;
  }

  for (const value of Object.values(node)) {
    if (value && typeof value === "object") {
      const cost = findEstimatedQueryCost(value);
      if (cost !== null && cost !== undefined) return cost;
    }
  }

  return null;
}

function collectTableOperations(node, result = []) {
  if (!node || typeof node !== "object") return result;

  if (Array.isArray(node)) {
    node.forEach((item) => collectTableOperations(item, result));
    return result;
  }

  const isTableOperation =
    node.table_name ||
    node.access_type ||
    node.rows_examined_per_scan !== undefined;

  if (isTableOperation) {
    result.push({
      table: node.table_name || node.table || "—",
      accessType: node.access_type || node.accessType || "—",
      rows:
        node.rows_examined_per_scan ??
        node.rows ??
        node.rows_examined ??
        "—",
      possibleKeys: node.possible_keys ?? node.possibleKeys ?? "—",
      chosenKey: node.key ?? node.chosen_key ?? "—",
      filtered: node.filtered ?? "—",
    });
  }

  Object.values(node).forEach((value) => {
    if (value && typeof value === "object") {
      collectTableOperations(value, result);
    }
  });

  return result;
}

function getFindings(analysis) {
  if (Array.isArray(analysis?.findings)) return analysis.findings;
  if (Array.isArray(analysis?.issues)) return analysis.issues;
  return [];
}

function getRecommendations(indexAnalysis) {
  if (Array.isArray(indexAnalysis?.recommendations)) {
    return indexAnalysis.recommendations;
  }

  if (Array.isArray(indexAnalysis?.index_recommendations)) {
    return indexAnalysis.index_recommendations;
  }

  return [];
}

function getExistingIndexes(indexAnalysis) {
  if (Array.isArray(indexAnalysis?.existing_indexes)) {
    return indexAnalysis.existing_indexes;
  }

  return [];
}

function getAccessClass(accessType) {
  return String(accessType).toLowerCase() === "all"
    ? "warning"
    : "normal";
}

function getSeverityClass(severity) {
  const value = String(severity || "info").toLowerCase();

  return ["critical", "high", "medium", "low"].includes(value)
    ? value
    : "info";
}

export default function ExecutionPlans() {
  const [connections, setConnections] = useState([]);
  const [selectedConnection, setSelectedConnection] = useState("");
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [result, setResult] = useState(null);

  const [loadingConnections, setLoadingConnections] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadConnections = useCallback(async () => {
    setLoadingConnections(true);
    setError("");

    try {
      const response = await api.getConnections();
      const items = getConnectionList(response);

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
    } catch (err) {
      setConnections([]);
      setSelectedConnection("");
      setError(
        err.message || "Unable to load your database connections."
      );
    } finally {
      setLoadingConnections(false);
    }
  }, []);

  useEffect(() => {
    loadConnections();
  }, [loadConnections]);

  const plan = useMemo(
    () => getPlanObject(result),
    [result]
  );

  const analysis = useMemo(
    () => getAnalysisObject(result),
    [result]
  );

  const indexAnalysis = useMemo(
    () => getIndexObject(result),
    [result]
  );

  const tableOperations = useMemo(() => {
    const source =
      analysis?.tables ??
      analysis?.table_operations ??
      plan;

    return collectTableOperations(source);
  }, [analysis, plan]);

  const findings = useMemo(
    () => getFindings(analysis),
    [analysis]
  );

  const recommendations = useMemo(
    () => getRecommendations(indexAnalysis),
    [indexAnalysis]
  );

  const existingIndexes = useMemo(
    () => getExistingIndexes(indexAnalysis),
    [indexAnalysis]
  );

  const estimatedQueryCost =
    analysis?.summary?.query_cost ??
    analysis?.summary?.estimated_query_cost ??
    analysis?.query_cost ??
    analysis?.estimated_query_cost ??
    findEstimatedQueryCost(plan);

  async function handleAnalyze(event) {
    event.preventDefault();

    setError("");
    setNotice("");
    setResult(null);

    if (!selectedConnection) {
      setError(
        "Add and select a database connection before analyzing an execution plan."
      );
      return;
    }

    if (!query.trim()) {
      setError("Enter a SELECT query.");
      return;
    }

    if (query.length > MAX_QUERY_LENGTH) {
      setError(
        `Query cannot exceed ${MAX_QUERY_LENGTH.toLocaleString()} characters.`
      );
      return;
    }

    try {
      setAnalyzing(true);

      const response = await api.explainQuery(
        query.trim(),
        Number(selectedConnection)
      );

      const returnedPlan = getPlanObject(response);

      if (!returnedPlan) {
        throw new Error(
          "The backend response did not contain an execution plan."
        );
      }

      setResult(response);

      setNotice(
        "Execution plan retrieved successfully. Estimated plan values are not actual execution timings."
      );
    } catch (err) {
      setError(
        err.message || "Unable to retrieve the execution plan."
      );
    } finally {
      setAnalyzing(false);
    }
  }

  function handleClear() {
    setQuery("");
    setResult(null);
    setError("");
    setNotice("");
  }

  return (
    <div className="execution-plans-page">
      <div className="execution-plans-header">
        <div>
          <h2>Execution Plan Analyzer</h2>
          <p>
            Inspect MySQL query plans, table access methods,
            and index recommendations.
          </p>
        </div>

        <button
          className="ep-refresh-button"
          type="button"
          onClick={loadConnections}
          disabled={loadingConnections || analyzing}
        >
          {loadingConnections
            ? "Loading..."
            : "↻ Refresh connections"}
        </button>
      </div>

      {error && (
        <div className="ep-alert error" role="alert">
          {error}
        </div>
      )}

      {notice && (
        <div className="ep-alert success" role="status">
          {notice}
        </div>
      )}

      <section className="ep-panel">
        <div className="ep-panel-heading">
          <div>
            <h3>Analyze a SQL execution plan</h3>
            <p>
              Uses MySQL EXPLAIN FORMAT=JSON.
              This does not execute the SELECT query.
            </p>
          </div>

          <span className="ep-readonly-badge">
            READ-ONLY ANALYSIS
          </span>
        </div>

        <form onSubmit={handleAnalyze}>
          <label className="ep-field">
            Database connection

            <select
              value={selectedConnection}
              onChange={(event) => {
                setSelectedConnection(event.target.value);
                setResult(null);
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

          <label className="ep-field">
            SQL SELECT query

            <textarea
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setError("");
                setNotice("");
              }}
              rows={8}
              spellCheck="false"
              placeholder="Enter a SELECT query to inspect..."
            />
          </label>

          <div className="ep-form-footer">
            <span>
              {query.length.toLocaleString()} /{" "}
              {MAX_QUERY_LENGTH.toLocaleString()} characters ·
              SELECT statements only
            </span>

            <div className="ep-actions">
              <button
                className="ep-secondary-button"
                type="button"
                onClick={handleClear}
                disabled={analyzing}
              >
                Clear
              </button>

              <button
                className="ep-primary-button"
                type="submit"
                disabled={
                  analyzing ||
                  loadingConnections ||
                  !connections.length ||
                  !query.trim() ||
                  query.length > MAX_QUERY_LENGTH
                }
              >
                {analyzing
                  ? "Analyzing plan..."
                  : "Analyze Execution Plan"}
              </button>
            </div>
          </div>
        </form>

        {!loadingConnections && connections.length === 0 && (
          <div className="ep-empty-inline">
            No database connections found. Open Database
            Connections and add a MySQL connection first.
          </div>
        )}
      </section>

      {!result && (
        <section className="ep-empty-state">
          <div className="ep-empty-icon">⌁</div>

          <h3>Execution plan results will appear here</h3>

          <p>
            Select a saved database, enter a SELECT query,
            and run the analysis to inspect table access
            and index usage.
          </p>
        </section>
      )}

      {result && (
        <div className="ep-results">
          <section className="ep-panel">
            <div className="ep-panel-heading">
              <div>
                <h3>Plan overview</h3>
                <p>
                  Summary derived from the returned MySQL execution plan.
                </p>
              </div>
            </div>

            <div className="ep-metrics-grid">
              <div className="ep-metric">
                <span>Tables inspected</span>
                <strong>
                  {formatValue(
                    analysis?.summary?.tables_count ??
                    analysis?.tables_count ??
                    tableOperations.length
                  )}
                </strong>
              </div>

              <div className="ep-metric">
                <span>Estimated query cost</span>
                <strong>
                  {formatValue(estimatedQueryCost)}
                </strong>
              </div>

              <div className="ep-metric">
                <span>Findings</span>
                <strong>{findings.length}</strong>
              </div>

              <div className="ep-metric">
                <span>Index recommendations</span>
                <strong>{recommendations.length}</strong>
              </div>
            </div>

            {analysis?.summary?.description && (
              <p className="ep-muted">
                {analysis.summary.description}
              </p>
            )}

            <p className="ep-muted">
              Query cost and estimated row counts are optimizer
              estimates, not measured execution times.
            </p>
          </section>

          <section className="ep-panel">
            <div className="ep-panel-heading">
              <div>
                <h3>Table access operations</h3>
                <p>
                  Access method and estimated row information
                  reported by MySQL.
                </p>
              </div>
            </div>

            {tableOperations.length > 0 ? (
              <div className="ep-table-scroll">
                <table className="ep-table">
                  <thead>
                    <tr>
                      <th>Table</th>
                      <th>Access type</th>
                      <th>Estimated rows</th>
                      <th>Possible keys</th>
                      <th>Selected key</th>
                      <th>Filtered</th>
                    </tr>
                  </thead>

                  <tbody>
                    {tableOperations.map((item, index) => (
                      <tr key={`${item.table}-${index}`}>
                        <td>{formatValue(item.table)}</td>

                        <td>
                          <span
                            className={`ep-access-tag ${getAccessClass(
                              item.accessType
                            )}`}
                          >
                            {formatValue(item.accessType)}
                          </span>
                        </td>

                        <td>{formatValue(item.rows)}</td>
                        <td>{formatValue(item.possibleKeys)}</td>
                        <td>{formatValue(item.chosenKey)}</td>
                        <td>{formatValue(item.filtered)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="ep-muted">
                No table-operation summary was returned in the
                expected structure. Expand the raw plan below
                to inspect the full MySQL response.
              </p>
            )}
          </section>

          <section className="ep-panel">
            <div className="ep-panel-heading">
              <div>
                <h3>Execution plan findings</h3>
                <p>
                  Potential scan and index-usage observations.
                </p>
              </div>
            </div>

            {findings.length > 0 ? (
              <div className="ep-findings">
                {findings.map((finding, index) => {
                  const severity = getSeverityClass(
                    finding.severity
                  );

                  return (
                    <article
                      className="ep-finding"
                      key={
                        finding.rule_id ||
                        finding.code ||
                        index
                      }
                    >
                      <div className="ep-finding-top">
                        <strong>
                          {finding.title ||
                            finding.message ||
                            finding.rule_id ||
                            "Plan finding"}
                        </strong>

                        <span
                          className={`ep-severity ${severity}`}
                        >
                          {finding.severity || "info"}
                        </span>
                      </div>

                      <p>
                        {finding.description ||
                          finding.detail ||
                          finding.message ||
                          "No additional description provided."}
                      </p>

                      {finding.recommendation && (
                        <div className="ep-recommendation">
                          <strong>Recommendation</strong>
                          <p>{finding.recommendation}</p>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className="ep-no-findings">
                No execution-plan findings were returned for this query.
              </div>
            )}
          </section>

          <section className="ep-panel">
            <div className="ep-panel-heading">
              <div>
                <h3>Index recommendations</h3>
                <p>
                  Suggestions only. QueryWise does not create
                  or modify indexes automatically.
                </p>
              </div>
            </div>

            {recommendations.length > 0 ? (
              <div className="ep-findings">
                {recommendations.map((item, index) => (
                  <article
                    className="ep-finding"
                    key={
                      item.index_name ||
                      item.table_name ||
                      index
                    }
                  >
                    <strong>
                      {item.title ||
                        item.table_name ||
                        item.table ||
                        "Index suggestion"}
                    </strong>

                    <p>
                      {item.explanation ||
                        item.reason ||
                        item.description ||
                        "Review this suggested index against your workload before applying it."}
                    </p>

                    {item.sql && (
                      <pre className="ep-sql-suggestion">
                        {item.sql}
                      </pre>
                    )}

                    {item.recommended_index && (
                      <pre className="ep-sql-suggestion">
                        {item.recommended_index}
                      </pre>
                    )}

                    {item.columns && (
                      <p>
                        Columns: {formatValue(item.columns)}
                      </p>
                    )}
                  </article>
                ))}
              </div>
            ) : (
              <div className="ep-no-findings">
                No index recommendations were generated.
                This can be appropriate for small tables or
                queries that already use suitable indexes.
              </div>
            )}

            {existingIndexes.length > 0 && (
              <details className="ep-details">
                <summary>View existing indexes</summary>
                <pre>
                  {JSON.stringify(existingIndexes, null, 2)}
                </pre>
              </details>
            )}
          </section>

          <section className="ep-panel">
            <details className="ep-details">
              <summary>
                View raw MySQL execution plan response
              </summary>

              <pre>
                {JSON.stringify(plan ?? result, null, 2)}
              </pre>
            </details>
          </section>
        </div>
      )}
    </div>
  );
}
