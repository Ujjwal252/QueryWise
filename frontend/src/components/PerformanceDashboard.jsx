
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import "./PerformanceDashboard.css";

const PAGE_SIZE = 20;

function hasValidExecutionTime(value) {
  return (
    value !== null &&
    value !== undefined &&
    value !== "" &&
    Number.isFinite(Number(value)) &&
    Number(value) >= 0
  );
}

function formatDuration(value) {
  if (!hasValidExecutionTime(value)) return "—";

  return `${Number(value).toFixed(3)} ms`;
}

function formatDate(value) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function PerformanceDashboard() {
  const [records, setRecords] = useState([]);
  const [totalRecords, setTotalRecords] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadPerformanceData = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await api.getQueryHistory({
        page: 1,
        perPage: PAGE_SIZE,
      });

      const data = response?.data;

      setRecords(
        Array.isArray(data?.records) ? data.records : []
      );

      setTotalRecords(
        Number(data?.pagination?.total_records || 0)
      );
    } catch (requestError) {
      setRecords([]);
      setTotalRecords(0);
      setError(
        requestError.message || "Unable to load performance data."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPerformanceData();
  }, [loadPerformanceData]);

  const metrics = useMemo(() => {
    const validTimes = records
      .filter((record) =>
        hasValidExecutionTime(record.execution_time_ms)
      )
      .map((record) => Number(record.execution_time_ms));

    const successful = records.filter(
      (record) => record.execution_status === "success"
    ).length;

    const failed = records.filter(
      (record) => record.execution_status === "failed"
    ).length;

    const average = validTimes.length
      ? validTimes.reduce((sum, value) => sum + value, 0) /
        validTimes.length
      : null;

    return {
      average,
      successful,
      failed,
      measured: validTimes.length,
    };
  }, [records]);

  const chartRecords = useMemo(() => {
    return [...records]
      .filter((record) =>
        hasValidExecutionTime(record.execution_time_ms)
      )
      .slice(0, 12)
      .reverse();
  }, [records]);

  const maxDuration = Math.max(
    1,
    ...chartRecords.map((record) =>
      Number(record.execution_time_ms)
    )
  );

  return (
    <section className="performance-page">
      <div className="performance-heading">
        <div>
          <h2>Performance Dashboard</h2>
          <p>
            Understand recorded query execution times and benchmark outcomes.
          </p>
        </div>

        <button
          type="button"
          className="performance-refresh"
          onClick={loadPerformanceData}
          disabled={loading}
        >
          {loading ? "Refreshing..." : "↻ Refresh"}
        </button>
      </div>

      {error && (
        <div className="performance-error">
          {error}
        </div>
      )}

      <div className="performance-metrics">
        <article className="performance-metric-card">
          <span>Recorded query runs</span>
          <strong>{totalRecords.toLocaleString()}</strong>
          <small>
            Total query history records for your account
          </small>
        </article>

        <article className="performance-metric-card">
          <span>Average execution time</span>
          <strong>
            {metrics.average === null
              ? "—"
              : formatDuration(metrics.average)}
          </strong>
          <small>
            Based on {metrics.measured} measured records on this page
          </small>
        </article>

        <article className="performance-metric-card">
          <span>Successful records</span>
          <strong>{metrics.successful.toLocaleString()}</strong>
          <small>
            Successful records on this page
          </small>
        </article>

        <article className="performance-metric-card">
          <span>Failed records</span>
          <strong>{metrics.failed.toLocaleString()}</strong>
          <small>
            Failed records on this page
          </small>
        </article>
      </div>

      <div className="performance-content-grid">
        <section className="performance-panel performance-chart-panel">
          <div className="performance-panel-heading">
            <div>
              <h3>Recent execution times</h3>
              <p>
                Latest 12 measured query records on this page
              </p>
            </div>
          </div>

          {loading ? (
            <div className="performance-empty">
              Loading performance data...
            </div>
          ) : chartRecords.length === 0 ? (
            <div className="performance-empty">
              No execution-time records are available yet.
              Run a performance comparison in SQL Workspace
              to populate this chart.
            </div>
          ) : (
            <div className="performance-bar-chart">
              {chartRecords.map((record) => {
                const duration = Number(
                  record.execution_time_ms
                );

                const width = Math.max(
                  2,
                  (duration / maxDuration) * 100
                );

                return (
                  <div
                    className="performance-bar-row"
                    key={record.query_id}
                  >
                    <div className="performance-bar-label">
                      <span>
                        #{record.query_id} ·{" "}
                        {record.query_type || "SQL"}
                      </span>

                      <strong>
                        {formatDuration(duration)}
                      </strong>
                    </div>

                    <div className="performance-bar-track">
                      <div
                        className="performance-bar-fill"
                        style={{ width: `${width}%` }}
                        title={`${duration.toFixed(3)} ms`}
                      />
                    </div>

                    <small>
                      {formatDate(record.created_at)}
                    </small>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <section className="performance-panel performance-notes-panel">
          <h3>How to read these metrics</h3>

          <div className="performance-note">
            <span className="performance-note-dot purple" />

            <div>
              <strong>Execution time</strong>
              <p>
                Measured duration stored for each query history record.
              </p>
            </div>
          </div>

          <div className="performance-note">
            <span className="performance-note-dot green" />

            <div>
              <strong>Successful records</strong>
              <p>
                Query records whose benchmark execution completed successfully.
              </p>
            </div>
          </div>

          <div className="performance-note">
            <span className="performance-note-dot red" />

            <div>
              <strong>Failed records</strong>
              <p>
                History records marked with a failed execution status.
              </p>
            </div>
          </div>

          <div className="performance-data-note">
            Original and optimized queries are stored as separate
            history records. This dashboard does not infer comparison
            pairs or claim that one query is faster based only on
            its position in history. Use the SQL Workspace comparison
            report to verify performance improvements and result equivalence.
          </div>
        </section>
      </div>

      <section className="performance-panel performance-table-panel">
        <div className="performance-panel-heading">
          <div>
            <h3>Recent benchmark records</h3>
            <p>
              Latest query execution measurements saved to Query History
            </p>
          </div>

          <span className="performance-record-count">
            {records.length} shown
          </span>
        </div>

        {loading ? (
          <div className="performance-empty">
            Loading records...
          </div>
        ) : records.length === 0 ? (
          <div className="performance-empty">
            No benchmark records found.
          </div>
        ) : (
          <div className="performance-table-wrap">
            <table className="performance-table">
              <thead>
                <tr>
                  <th>Query ID</th>
                  <th>Query type</th>
                  <th>Execution time</th>
                  <th>Rows returned</th>
                  <th>Status</th>
                  <th>Recorded at</th>
                </tr>
              </thead>

              <tbody>
                {records.map((record) => (
                  <tr key={record.query_id}>
                    <td>#{record.query_id}</td>

                    <td>{record.query_type || "—"}</td>

                    <td>
                      {formatDuration(record.execution_time_ms)}
                    </td>

                    <td>
                      {record.rows_returned == null
                        ? "—"
                        : Number(
                            record.rows_returned
                          ).toLocaleString()}
                    </td>

                    <td>
                      <span
                        className={`performance-status ${
                          record.execution_status || "pending"
                        }`}
                      >
                        {record.execution_status || "pending"}
                      </span>
                    </td>

                    <td>{formatDate(record.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  );
}

export default PerformanceDashboard;
