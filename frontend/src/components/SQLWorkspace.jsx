
import { useEffect, useState } from "react";
import { api } from "../services/api";
import "./SQLWorkspace.css";
function SQLWorkspace() {
  const [query, setQuery] = useState(
    "SELECT * FROM employees WHERE department = 'Engineering';"
  );

  const [connections, setConnections] = useState([]);
  const [selectedConnection, setSelectedConnection] = useState("");

  const [analysis, setAnalysis] = useState(null);
  const [optimization, setOptimization] = useState(null);
  const [executionResult, setExecutionResult] = useState(null);
  const [comparisonResult, setComparisonResult] = useState(null);

  const [loadingConnections, setLoadingConnections] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [explaining, setExplaining] = useState(false);
  const [comparing, setComparing] = useState(false);

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [activeTab, setActiveTab] = useState("analysis");

  useEffect(() => {
    let mounted = true;

    async function loadConnections() {
      try {
        setLoadingConnections(true);

        const response = await api.getConnections();

        if (mounted) {
          const savedConnections = response.connections || [];
          setConnections(savedConnections);

          if (savedConnections.length > 0) {
            setSelectedConnection(
              String(savedConnections[0].connection_id)
            );
          }
        }
      } catch (err) {
        if (mounted) {
          setError(err.message || "Unable to load database connections.");
        }
      } finally {
        if (mounted) {
          setLoadingConnections(false);
        }
      }
    }

    loadConnections();

    return () => {
      mounted = false;
    };
  }, []);

  function handleQueryChange(event) {
    setQuery(event.target.value);
    setAnalysis(null);
    setOptimization(null);
    setExecutionResult(null);
    setComparisonResult(null);
    setError("");
    setMessage("");
  }

  async function handleAnalyze() {
    setError("");
    setMessage("");
    setAnalysis(null);

    if (!query.trim()) {
      setError("Please enter an SQL query first.");
      return;
    }

    try {
      setAnalyzing(true);
      setActiveTab("analysis");

      const response = await api.analyzeQuery(query);

      setAnalysis(response.data);
      setMessage(response.message || "Query analysis completed.");
    } catch (err) {
      setError(err.message || "Query analysis failed.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleOptimize() {
    setError("");
    setMessage("");
    setOptimization(null);

    if (!query.trim()) {
      setError("Please enter an SQL query first.");
      return;
    }

    try {
      setOptimizing(true);
      setActiveTab("optimization");

      const response = await api.optimizeQuery(query);

      setOptimization(response.data);
      setMessage(response.message || "Query optimization completed.");
    } catch (err) {
      setError(err.message || "Query optimization failed.");
    } finally {
      setOptimizing(false);
    }
  }

  async function handleExplain() {
    setError("");
    setMessage("");
    setExecutionResult(null);

    if (!query.trim()) {
      setError("Please enter an SQL query first.");
      return;
    }

    if (!selectedConnection) {
      setError("Please select a database connection first.");
      return;
    }

    try {
      setExplaining(true);
      setActiveTab("execution");

      const response = await api.explainQuery(
        query,
        Number(selectedConnection)
      );

      setExecutionResult(response.data);
      setMessage(
        response.message || "Execution plan analysis completed."
      );
    } catch (err) {
      setError(err.message || "Execution plan analysis failed.");
    } finally {
      setExplaining(false);
    }
  }

  async function handleCompare() {
    setError("");
    setMessage("");
    setComparisonResult(null);

    if (!selectedConnection) {
      setError("Please select a database connection first.");
      return;
    }

    if (!optimization?.original_query || !optimization?.optimized_query) {
      setError("Optimize the query first to generate an alternative for comparison.");
      return;
    }

    if (
      optimization.original_query.trim() ===
      optimization.optimized_query.trim()
    ) {
      setError("The optimizer did not generate a different query. There is nothing to compare.");
      return;
    }

    try {
      setComparing(true);
      setActiveTab("comparison");

      const response = await api.compareQueries({
        originalQuery: optimization.original_query,
        optimizedQuery: optimization.optimized_query,
        connectionId: Number(selectedConnection),
        iterations: 10,
        warmupRuns: 2,
      });

      setComparisonResult(response.data);
      setMessage(response.message || "Performance comparison completed.");
    } catch (err) {
      setError(err.message || "Performance comparison failed.");
    } finally {
      setComparing(false);
    }
  }

  async function handleCopy() {
    if (!optimization?.optimized_query) return;

    try {
      await navigator.clipboard.writeText(
        optimization.optimized_query
      );
      setMessage("Optimized SQL copied to clipboard.");
      setError("");
    } catch {
      setError("Unable to copy SQL. Please copy it manually.");
    }
  }

  function handleUseOptimizedQuery() {
    if (!optimization?.optimized_query) return;

    setQuery(optimization.optimized_query);
    setAnalysis(null);
    setOptimization(null);
    setExecutionResult(null);
    setComparisonResult(null);
    setError("");
    setMessage("Optimized query loaded into the editor.");
  }

  function handleClear() {
    setQuery("");
    setAnalysis(null);
    setOptimization(null);
    setExecutionResult(null);
    setComparisonResult(null);
    setError("");
    setMessage("");
  }

  function getSeverityClass(severity) {
    const normalized = String(severity || "").toLowerCase();

    if (normalized === "critical") return "severity-critical";
    if (normalized === "high") return "severity-high";
    if (normalized === "medium") return "severity-medium";
    if (normalized === "low") return "severity-low";

    return "severity-info";
  }

  function formatValue(value) {
    if (value === null || value === undefined) return "—";

    if (typeof value === "object") {
      return JSON.stringify(value);
    }

    return String(value);
  }

  function renderJson(value) {
    return JSON.stringify(value ?? {}, null, 2);
  }

  const findings = Array.isArray(analysis?.findings)
    ? analysis.findings
    : [];

  const techniques = Array.isArray(optimization?.techniques)
    ? optimization.techniques
    : [];

  const executionAnalysis = executionResult?.analysis || {};
  const executionSummary = executionAnalysis.summary || {};

  const executionTables = Array.isArray(executionAnalysis.tables)
    ? executionAnalysis.tables
    : [];

  const executionFindings = Array.isArray(executionAnalysis.findings)
    ? executionAnalysis.findings
    : [];

  const indexAnalysis = executionResult?.index_analysis || {};

  const existingIndexes = Array.isArray(indexAnalysis.existing_indexes)
    ? indexAnalysis.existing_indexes
    : [];

  // Backend returns recommendations as an OBJECT containing arrays.
  const recommendationData = indexAnalysis.recommendations || {};

  const indexRecommendations = Array.isArray(
    recommendationData.recommendations
  )
    ? recommendationData.recommendations
    : [];

  const skippedCandidates = Array.isArray(
    recommendationData.skipped_candidates
  )
    ? recommendationData.skipped_candidates
    : [];

  const recommendationCount =
    recommendationData.recommendations_count ??
    indexRecommendations.length;

  const skippedCount =
    recommendationData.skipped_candidates_count ??
    skippedCandidates.length;

  return (
    <div className="sql-workspace">
      <div className="sql-workspace-header">
        <div>
          <h2>SQL Query Workspace</h2>
          <p>
            Analyze your SQL queries and generate optimization alternatives.
          </p>
        </div>

        <div className="sql-workspace-badge">
          Read-only SQL
        </div>
      </div>

      {error && (
        <div className="sql-alert error" role="alert">
          {error}
        </div>
      )}

      {message && (
        <div className="sql-alert success" role="status">
          {message}
        </div>
      )}

      <section className="sql-connection-selector">
        <div>
          <label htmlFor="sql-connection">
            Active Database Connection
          </label>

          <p>Select the database you want to inspect.</p>
        </div>

        <select
          id="sql-connection"
          value={selectedConnection}
          onChange={(event) =>
            setSelectedConnection(event.target.value)
          }
          disabled={loadingConnections || connections.length === 0}
        >
          {loadingConnections ? (
            <option value="">Loading connections...</option>
          ) : connections.length === 0 ? (
            <option value="">No database connections available</option>
          ) : (
            connections.map((connection) => (
              <option
                key={connection.connection_id}
                value={String(connection.connection_id)}
              >
                {connection.connection_name} — {connection.database_name}
              </option>
            ))
          )}
        </select>
      </section>

      <section className="sql-editor-panel">
        <div className="sql-editor-heading">
          <div>
            <h3>SQL Editor</h3>
            <p>Write or paste your SELECT query below.</p>
          </div>

          <span className="sql-language-label">MySQL</span>
        </div>

        <div className="sql-editor-container">
          <div className="sql-editor-toolbar">
            <span>QUERY.SQL</span>
            <span>Read-only mode</span>
          </div>

          <textarea
            className="sql-editor"
            value={query}
            onChange={handleQueryChange}
            placeholder="Write your SELECT query here..."
            spellCheck="false"
            aria-label="SQL query editor"
          />
        </div>

        <div className="sql-editor-footer">
          <span>{query.length} characters</span>

          <button
            type="button"
            className="sql-clear-button"
            onClick={handleClear}
          >
            Clear Editor
          </button>
        </div>

        <div className="sql-action-buttons">
          <button
            type="button"
            className="sql-analyze-button"
            onClick={handleAnalyze}
            disabled={analyzing || optimizing || explaining || !query.trim()}
          >
            {analyzing ? "Analyzing..." : "Analyze Query"}
          </button>

          <button
            type="button"
            className="sql-optimize-button"
            onClick={handleOptimize}
            disabled={analyzing || optimizing || explaining || !query.trim()}
          >
            {optimizing ? "Optimizing..." : "Optimize Query"}
          </button>

          <button
            type="button"
            className="sql-explain-button"
            onClick={handleExplain}
            disabled={
              analyzing ||
              optimizing ||
              explaining ||
              comparing ||
              !query.trim() ||
              !selectedConnection
            }
          >
            {explaining ? "Analyzing Plan..." : "Execution Plan"}
          </button>

          <button
            type="button"
            className="sql-compare-button"
            onClick={handleCompare}
            disabled={
              analyzing ||
              optimizing ||
              explaining ||
              comparing ||
              !selectedConnection ||
              !optimization?.optimized_query ||
              optimization.original_query?.trim() ===
                optimization.optimized_query?.trim()
            }
          >
            {comparing ? "Comparing..." : "Compare Performance"}
          </button>
        </div>
      </section>

      <section className="sql-results-panel">
        <div className="sql-results-heading">
          <div>
            <h3>Query Results</h3>
            <p>
              Analysis findings, optimization suggestions, and execution plans.
            </p>
          </div>
        </div>

        <div className="sql-result-tabs">
          <button
            type="button"
            className={activeTab === "analysis" ? "active" : ""}
            onClick={() => setActiveTab("analysis")}
          >
            Query Analysis
          </button>

          <button
            type="button"
            className={activeTab === "optimization" ? "active" : ""}
            onClick={() => setActiveTab("optimization")}
          >
            Optimized SQL
          </button>

          <button
            type="button"
            className={activeTab === "execution" ? "active" : ""}
            onClick={() => setActiveTab("execution")}
          >
            Execution Plan
          </button>

          <button
            type="button"
            className={activeTab === "comparison" ? "active" : ""}
            onClick={() => setActiveTab("comparison")}
          >
            Performance Comparison
          </button>
        </div>

        {activeTab === "analysis" && (
          <div className="sql-result-content">
            {!analysis ? (
              <div className="sql-empty-result">
                <div className="sql-empty-icon">⌕</div>
                <h4>No Analysis Available</h4>
                <p>
                  Click Analyze Query to inspect your SQL query
                  and identify potential performance issues.
                </p>
              </div>
            ) : (
              <>
                <div className="sql-result-summary">
                  <div>
                    <span>Statement Type</span>
                    <strong>
                      {analysis.statement_type || "SELECT"}
                    </strong>
                  </div>

                  <div>
                    <span>Findings</span>
                    <strong>
                      {analysis.findings_count ?? findings.length}
                    </strong>
                  </div>
                </div>

                {findings.length === 0 ? (
                  <div className="sql-no-findings">
                    No potential optimization issues were detected
                    by the current analysis rules.
                  </div>
                ) : (
                  <div className="sql-findings-list">
                    {findings.map((finding, index) => (
                      <article
                        className="sql-finding-card"
                        key={finding.rule_id || index}
                      >
                        <div className="sql-finding-top">
                          <span className="sql-rule-id">
                            {finding.rule_id}
                          </span>

                          <span
                            className={`sql-severity ${getSeverityClass(
                              finding.severity
                            )}`}
                          >
                            {finding.severity}
                          </span>
                        </div>

                        <h4>{finding.title}</h4>
                        <p>{finding.description}</p>

                        <div className="sql-recommendation">
                          <strong>Recommendation:</strong>
                          <p>{finding.recommendation}</p>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {activeTab === "optimization" && (
          <div className="sql-result-content">
            {!optimization ? (
              <div className="sql-empty-result">
                <div className="sql-empty-icon">⚙</div>
                <h4>No Optimized Query Yet</h4>
                <p>
                  Click Optimize Query to generate a conservative
                  SQL rewrite where supported.
                </p>
              </div>
            ) : (
              <div className="sql-optimization-result">
                <div className="sql-optimization-heading">
                  <div>
                    <h4>Optimized SQL Alternative</h4>
                    <p>Review the generated query before using it.</p>
                  </div>

                  <span className="sql-language-label">MySQL</span>
                </div>

                <pre className="sql-optimized-code">
                  <code>{optimization.optimized_query}</code>
                </pre>

                <div className="sql-optimization-actions">
                  <button
                    type="button"
                    className="sql-copy-button"
                    onClick={handleCopy}
                  >
                    Copy SQL
                  </button>

                  <button
                    type="button"
                    className="sql-use-button"
                    onClick={handleUseOptimizedQuery}
                  >
                    Use in Editor
                  </button>
                </div>

                <div className="sql-techniques-section">
                  <h4>
                    Optimization Techniques ({techniques.length})
                  </h4>

                  {techniques.length === 0 ? (
                    <p>
                      No optimization techniques were required.
                      The generated query is unchanged.
                    </p>
                  ) : (
                    <ul>
                      {techniques.map((technique, index) => (
                        <li key={`${technique}-${index}`}>
                          {technique}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {optimization.explanation && (
                  <div className="sql-explanation">
                    <h4>Explanation</h4>
                    <p>{optimization.explanation}</p>
                  </div>
                )}

                <div className="sql-validation-note">
                  A generated SQL alternative is not a guarantee
                  of equivalent results or faster execution.
                  Validate it before relying on it.
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "execution" && (
          <div className="sql-result-content">
            {!executionResult ? (
              <div className="sql-empty-result">
                <div className="sql-empty-icon">⌁</div>
                <h4>No Execution Plan Available</h4>
                <p>
                  Select a database connection and click Execution Plan
                  to inspect the MySQL execution plan and index analysis.
                </p>
              </div>
            ) : (
              <div className="sql-execution-result">
                <div className="sql-result-summary">
                  <div>
                    <span>Connection ID</span>
                    <strong>{executionResult.connection_id}</strong>
                  </div>

                  <div>
                    <span>Tables Checked</span>
                    <strong>
                      {Array.isArray(indexAnalysis.tables_checked)
                        ? indexAnalysis.tables_checked.length
                        : executionTables.length}
                    </strong>
                  </div>

                  <div>
                    <span>Existing Indexes</span>
                    <strong>
                      {indexAnalysis.existing_indexes_count ??
                        existingIndexes.length}
                    </strong>
                  </div>

                  <div>
                    <span>Index Recommendations</span>
                    <strong>{recommendationCount}</strong>
                  </div>
                </div>

                <div className="sql-execution-section">
                  <h4>Execution Plan Summary</h4>

                  <div className="sql-execution-grid">
                    {Object.entries(executionSummary).map(
                      ([key, value]) => (
                        <div className="sql-execution-item" key={key}>
                          <span>{key.replaceAll("_", " ")}</span>
                          <strong>{formatValue(value)}</strong>
                        </div>
                      )
                    )}
                  </div>
                </div>

                <div className="sql-execution-section">
                  <h4>Table Access Information</h4>

                  {executionTables.length === 0 ? (
                    <p className="sql-secondary-text">
                      No table access information was returned.
                    </p>
                  ) : (
                    <div className="sql-table-scroll">
                      <table className="sql-data-table">
                        <thead>
                          <tr>
                            <th>Table</th>
                            <th>Access Type</th>
                            <th>Rows Examined</th>
                            <th>Index Used</th>
                          </tr>
                        </thead>

                        <tbody>
                          {executionTables.map((table, index) => (
                            <tr key={`${table.table_name || "table"}-${index}`}>
                              <td>{formatValue(table.table_name)}</td>
                              <td>{formatValue(table.access_type)}</td>
                              <td>
                                {formatValue(table.rows_examined_per_scan)}
                              </td>
                              <td>{formatValue(table.selected_key)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                <div className="sql-execution-section">
                  <h4>
                    Execution Plan Findings ({executionFindings.length})
                  </h4>

                  {executionFindings.length === 0 ? (
                    <p className="sql-secondary-text">
                      No execution-plan findings were returned.
                    </p>
                  ) : (
                    <div className="sql-findings-list">
                      {executionFindings.map((finding, index) => (
                        <article
                          className="sql-finding-card"
                          key={finding.rule_id || index}
                        >
                          <div className="sql-finding-top">
                            <span className="sql-rule-id">
                              {finding.rule_id || "Finding"}
                            </span>

                            <span
                              className={`sql-severity ${getSeverityClass(
                                finding.severity
                              )}`}
                            >
                              {finding.severity || "info"}
                            </span>
                          </div>

                          <h4>{finding.title}</h4>
                          <p>{finding.description}</p>

                          {finding.recommendation && (
                            <div className="sql-recommendation">
                              <strong>Recommendation:</strong>
                              <p>{finding.recommendation}</p>
                            </div>
                          )}
                        </article>
                      ))}
                    </div>
                  )}
                </div>

                <div className="sql-execution-section">
                  <h4>Existing Database Indexes</h4>

                  {existingIndexes.length === 0 ? (
                    <p className="sql-secondary-text">
                      No index metadata was returned.
                    </p>
                  ) : (
                    <div className="sql-table-scroll">
                      <table className="sql-data-table">
                        <thead>
                          <tr>
                            <th>Table</th>
                            <th>Column</th>
                            <th>Index Name</th>
                            <th>Index Type</th>
                            <th>Unique</th>
                          </tr>
                        </thead>

                        <tbody>
                          {existingIndexes.map((index, position) => (
                            <tr
                              key={`${index.index_name}-${index.column_name}-${position}`}
                            >
                              <td>{formatValue(index.table_name)}</td>
                              <td>{formatValue(index.column_name)}</td>
                              <td>{formatValue(index.index_name)}</td>
                              <td>{formatValue(index.index_type)}</td>
                              <td>
                                {index.non_unique === undefined
                                  ? "—"
                                  : index.non_unique === 0
                                    ? "Yes"
                                    : "No"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                <div className="sql-execution-section">
                  <h4>
                    Index Recommendations ({recommendationCount})
                  </h4>

                  {indexRecommendations.length === 0 ? (
                    <div className="sql-no-findings">
                      No additional indexes are recommended for this query.
                    </div>
                  ) : (
                    <div className="sql-findings-list">
                      {indexRecommendations.map((recommendation, index) => (
                        <article
                          className="sql-finding-card"
                          key={recommendation.recommendation_id || index}
                        >
                          <h4>
                            {recommendation.title ||
                              recommendation.table_name ||
                              "Index Recommendation"}
                          </h4>

                          <p>
                            {recommendation.description ||
                              "The analyzer identified a possible indexing opportunity."}
                          </p>

                          <div className="sql-recommendation">
                            <strong>Recommendation details:</strong>
                            <pre>{renderJson(recommendation)}</pre>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}

                  {skippedCandidates.length > 0 && (
                    <div className="sql-skipped-candidates">
                      <h4>
                        Skipped Index Candidates ({skippedCount})
                      </h4>

                      <p>
                        These candidates were considered but not recommended.
                      </p>

                      {skippedCandidates.map((candidate, index) => (
                        <article
                          className="sql-skipped-card"
                          key={`${candidate.table_name}-${candidate.column_name}-${index}`}
                        >
                          <strong>
                            {candidate.table_name}.{candidate.column_name}
                          </strong>

                          <span>
                            Estimated rows: {formatValue(candidate.estimated_rows)}
                          </span>

                          <p>{candidate.reason}</p>
                        </article>
                      ))}
                    </div>
                  )}

                  <p className="sql-secondary-text">
                    Automatic index creation:{" "}
                    {recommendationData.automatic_index_creation
                      ? "Enabled"
                      : "Disabled"}
                  </p>
                </div>

                <details className="sql-raw-plan">
                  <summary>View Raw MySQL JSON Execution Plan</summary>
                  <pre>
                    {renderJson(executionResult.execution_plan)}
                  </pre>
                </details>

                <div className="sql-validation-note">
                  Execution-plan costs and row estimates are MySQL optimizer
                  estimates, not actual query execution time. Index
                  recommendations are advisory. QueryWise does not
                  automatically create indexes.
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "comparison" && (
          <div className="sql-result-content">
            {!comparisonResult ? (
              <div className="sql-empty-result">
                <div className="sql-empty-icon">↔</div>
                <h4>No Performance Comparison Available</h4>
                <p>
                  First optimize a query, then click Compare Performance to
                  benchmark the original and optimized alternatives.
                </p>
              </div>
            ) : (
              <div className="sql-comparison-result">
                {(() => {
                  const original = comparisonResult.original_query || {};
                  const optimized = comparisonResult.optimized_query || {};
                  const comparison = comparisonResult.comparison || {};
                  const paired = comparison.paired_performance_analysis || {};
                  const originalStats = original.statistics || {};
                  const optimizedStats = optimized.statistics || {};
                  const assessment = comparison.optimization_assessment || "inconclusive";
                  const successful = comparison.optimization_successful === true;
                  const equivalenceVerified = comparison.result_equivalence_verified === true;
                  const equivalent = comparison.result_equivalent;

                  const labelForAssessment = {
                    faster_and_equivalent: "Faster and result-equivalent",
                    performance_regression: "Performance regression detected",
                    not_equivalent: "Results are not equivalent",
                    equivalence_not_verified: "Result equivalence not verified",
                    inconclusive: "Performance result is inconclusive",
                  }[assessment] || assessment.replaceAll("_", " ");

                  // Overall status follows paired benchmark reliability,
                  // not only the aggregate average execution times.
                  const reliability = paired.performance_reliability || "inconclusive";
                  const pairedStatusLabel =
                    assessment === "performance_regression" ||
                    reliability === "performance_regression"
                      ? "Regression"
                      : assessment === "faster_and_equivalent"
                        ? "Consistently faster"
                        : assessment === "not_equivalent"
                          ? "Not validated"
                          : assessment === "equivalence_not_verified"
                            ? "Equivalence unverified"
                            : "Inconclusive";

                  const metric = (stats, key) => {
                    const value = stats[key];
                    return value === null || value === undefined ? "—" : `${value} ms`;
                  };

                  return (
                    <>
                      <div className={`sql-comparison-assessment ${successful ? "success" : "caution"}`}>
                        <strong>{labelForAssessment}</strong>
                        <p>
                          {successful
                            ? "The optimized query returned equivalent results and showed a consistent performance improvement in the measured rounds."
                            : "QueryWise did not confirm a consistently faster, equivalent optimization. Review the measurements and validation status before using the alternative."}
                        </p>
                      </div>

                      <div className="sql-result-summary">
                        <div>
                          <span>Average time improvement</span>
                          <strong>{formatValue(comparison.improvement_percentage)}%</strong>
                        </div>
                        <div>
                          <span>Average time difference</span>
                          <strong>{formatValue(comparison.time_difference_ms)} ms</strong>
                        </div>
                        <div>
                          <span>Paired performance status</span>
                          <strong>{pairedStatusLabel}</strong>
                        </div>
                        <div>
                          <span>Result equivalence</span>
                          <strong>{!equivalenceVerified ? "Not verified" : equivalent ? "Equivalent" : "Not equivalent"}</strong>
                        </div>
                      </div>

                      <div className="sql-execution-section">
                        <h4>Execution Time Comparison</h4>
                        <div className="sql-table-scroll">
                          <table className="sql-data-table">
                            <thead>
                              <tr><th>Metric</th><th>Original Query</th><th>Optimized Query</th></tr>
                            </thead>
                            <tbody>
                              <tr><td>Average</td><td>{metric(originalStats, "average_ms")}</td><td>{metric(optimizedStats, "average_ms")}</td></tr>
                              <tr><td>Median</td><td>{metric(originalStats, "median_ms")}</td><td>{metric(optimizedStats, "median_ms")}</td></tr>
                              <tr><td>Minimum</td><td>{metric(originalStats, "minimum_ms")}</td><td>{metric(optimizedStats, "minimum_ms")}</td></tr>
                              <tr><td>Maximum</td><td>{metric(originalStats, "maximum_ms")}</td><td>{metric(optimizedStats, "maximum_ms")}</td></tr>
                              <tr><td>Rows returned</td><td>{formatValue(original.rows_returned)}</td><td>{formatValue(optimized.rows_returned)}</td></tr>
                            </tbody>
                          </table>
                        </div>
                      </div>

                      <div className="sql-execution-section">
                        <h4>Paired Benchmark Reliability</h4>
                        <div className="sql-result-summary">
                          <div><span>Total rounds</span><strong>{formatValue(paired.total_rounds)}</strong></div>
                          <div><span>Optimized faster</span><strong>{formatValue(paired.faster_rounds)}</strong></div>
                          <div><span>Optimized slower</span><strong>{formatValue(paired.slower_rounds)}</strong></div>
                          <div><span>Equal rounds</span><strong>{formatValue(paired.equal_rounds)}</strong></div>
                          <div><span>Median paired improvement</span><strong>{formatValue(paired.median_paired_improvement_ms)} ms</strong></div>
                          <div><span>Reliability</span><strong>{formatValue(reliability)}</strong></div>
                        </div>
                      </div>

                      <div className="sql-execution-section">
                        <h4>Correctness Validation</h4>
                        <p>
                          Equivalence verified: <strong>{equivalenceVerified ? "Yes" : "No"}</strong>
                          {" · "}Equivalent results: <strong>{equivalent === null || equivalent === undefined ? "Unknown" : equivalent ? "Yes" : "No"}</strong>
                        </p>
                        <p>
                          Column names match: <strong>{formatValue(comparison.column_names_match)}</strong>
                          {" · "}Row count matches: <strong>{formatValue(comparison.row_count_match)}</strong>
                          {" · "}Result order matters: <strong>{formatValue(comparison.result_order_matters)}</strong>
                        </p>
                        {comparison.equivalence_mismatch_reason && (
                          <p className="sql-secondary-text">Reason: {comparison.equivalence_mismatch_reason}</p>
                        )}
                      </div>

                      <div className="sql-execution-section">
                        <h4>Queries Compared</h4>
                        <p className="sql-secondary-text">Original query</p>
                        <pre className="sql-optimized-code"><code>{original.sql || ""}</code></pre>
                        <p className="sql-secondary-text">Optimized query</p>
                        <pre className="sql-optimized-code"><code>{optimized.sql || ""}</code></pre>
                      </div>

                      <div className="sql-validation-note">
                        Average time improvement is a descriptive aggregate and does not establish a reliable speedup by itself. The overall performance status is based on paired benchmark consistency and result validation. Timings can vary with caching, server load, and database activity; estimated execution-plan cost is not actual runtime. Treat small differences cautiously.
                      </div>
                    </>
                  );
                })()}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

export default SQLWorkspace;
