import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api";
import "./QueryHistory.css";

const PAGE_SIZE = 20;

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatDuration(value) {
  if (value === null || value === undefined || value === "") return "—";
  const milliseconds = Number(value);
  return Number.isFinite(milliseconds) ? `${milliseconds.toFixed(3)} ms` : "—";
}

function formatRows(value) {
  if (value === null || value === undefined) return "—";
  return Number(value).toLocaleString();
}

function QueryHistory() {
  const [records, setRecords] = useState([]);
  const [pagination, setPagination] = useState({
    page: 1,
    per_page: PAGE_SIZE,
    total_records: 0,
    total_pages: 0,
    has_next: false,
    has_previous: false,
  });
  const [queryType, setQueryType] = useState("");
  const [executionStatus, setExecutionStatus] = useState("");
  const [page, setPage] = useState(1);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await api.getQueryHistory({
        page,
        perPage: PAGE_SIZE,
        queryType,
        executionStatus,
      });
      const data = response?.data;
      setRecords(Array.isArray(data?.records) ? data.records : []);
      setPagination(data?.pagination || {
        page,
        per_page: PAGE_SIZE,
        total_records: 0,
        total_pages: 0,
        has_next: false,
        has_previous: false,
      });
    } catch (requestError) {
      setRecords([]);
      setError(requestError.message || "Unable to load query history.");
    } finally {
      setLoading(false);
    }
  }, [page, queryType, executionStatus]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  function handleQueryTypeChange(event) {
    setPage(1);
    setQueryType(event.target.value);
    setSelectedRecord(null);
  }

  function handleStatusChange(event) {
    setPage(1);
    setExecutionStatus(event.target.value);
    setSelectedRecord(null);
  }

  async function handleCopy(query) {
    try {
      await navigator.clipboard.writeText(query || "");
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setError("Unable to copy SQL. Check your browser clipboard permissions.");
    }
  }

  function clearFilters() {
    setQueryType("");
    setExecutionStatus("");
    setPage(1);
    setSelectedRecord(null);
  }

  return (
    <section className="history-page">
      <div className="history-header">
        <div>
          <h2>Query History</h2>
          <p>Review previously benchmarked SQL queries and their execution details.</p>
        </div>
        <button
          type="button"
          className="history-refresh-button"
          onClick={loadHistory}
          disabled={loading}
        >
          {loading ? "Refreshing..." : "↻ Refresh"}
        </button>
      </div>

      <div className="history-summary-grid">
        <div className="history-summary-card">
          <span>Total records</span>
          <strong>{Number(pagination.total_records || 0).toLocaleString()}</strong>
        </div>
        <div className="history-summary-card">
          <span>Current page</span>
          <strong>{pagination.page || page}</strong>
        </div>
        <div className="history-summary-card">
          <span>Records per page</span>
          <strong>{pagination.per_page || PAGE_SIZE}</strong>
        </div>
      </div>

      <div className="history-panel">
        <div className="history-filter-row">
          <div className="history-filter">
            <label htmlFor="history-query-type">Query type</label>
            <select
              id="history-query-type"
              value={queryType}
              onChange={handleQueryTypeChange}
            >
              <option value="">All query types</option>
              <option value="SELECT">SELECT</option>
              <option value="INSERT">INSERT</option>
              <option value="UPDATE">UPDATE</option>
              <option value="DELETE">DELETE</option>
            </select>
          </div>

          <div className="history-filter">
            <label htmlFor="history-status">Execution status</label>
            <select
              id="history-status"
              value={executionStatus}
              onChange={handleStatusChange}
            >
              <option value="">All statuses</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
              <option value="pending">Pending</option>
            </select>
          </div>

          <button
            type="button"
            className="history-clear-button"
            onClick={clearFilters}
            disabled={!queryType && !executionStatus}
          >
            Clear filters
          </button>
        </div>

        {error && <div className="history-alert error">{error}</div>}

        {loading ? (
          <div className="history-state">Loading query history...</div>
        ) : records.length === 0 ? (
          <div className="history-state">
            <div className="history-empty-icon">◷</div>
            <h3>No query history found</h3>
            <p>
              Completed performance comparisons will appear here. Try changing
              your filters or run a comparison in SQL Workspace.
            </p>
          </div>
        ) : (
          <>
            <div className="history-table-wrap">
              <table className="history-table">
                <thead>
                  <tr>
                    <th>Query</th>
                    <th>Connection</th>
                    <th>Type</th>
                    <th>Execution time</th>
                    <th>Rows</th>
                    <th>Status</th>
                    <th>Date</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((record) => (
                    <tr key={record.query_id}>
                      <td className="history-query-cell">
                        <code>{(record.original_query || "").replace(/\s+/g, " ").trim()}</code>
                      </td>
                      <td>{record.connection_name || `Connection #${record.connection_id}`}</td>
                      <td><span className="history-type">{record.query_type || "—"}</span></td>
                      <td className="history-number">{formatDuration(record.execution_time_ms)}</td>
                      <td className="history-number">{formatRows(record.rows_returned)}</td>
                      <td>
                        <span className={`history-status ${String(record.execution_status || "pending").toLowerCase()}`}>
                          {record.execution_status || "pending"}
                        </span>
                      </td>
                      <td className="history-date">{formatDate(record.created_at)}</td>
                      <td>
                        <button
                          type="button"
                          className="history-view-button"
                          onClick={() => {
                            setSelectedRecord(record);
                            setCopied(false);
                          }}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="history-pagination">
              <span>
                Showing {records.length} of {Number(pagination.total_records || 0).toLocaleString()} records
              </span>
              <div className="history-pagination-actions">
                <button
                  type="button"
                  onClick={() => {
                    setPage((current) => Math.max(1, current - 1));
                    setSelectedRecord(null);
                  }}
                  disabled={!pagination.has_previous || loading}
                >
                  Previous
                </button>
                <span>Page {pagination.page || page} of {pagination.total_pages || 1}</span>
                <button
                  type="button"
                  onClick={() => {
                    setPage((current) => current + 1);
                    setSelectedRecord(null);
                  }}
                  disabled={!pagination.has_next || loading}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {selectedRecord && (
        <div
          className="history-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setSelectedRecord(null);
          }}
        >
          <section
            className="history-detail-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="history-detail-title"
          >
            <div className="history-detail-header">
              <div>
                <span>Query #{selectedRecord.query_id}</span>
                <h3 id="history-detail-title">Query details</h3>
              </div>
              <button
                type="button"
                className="history-modal-close"
                onClick={() => setSelectedRecord(null)}
                aria-label="Close query details"
              >
                ×
              </button>
            </div>

            <div className="history-detail-grid">
              <div><span>Connection</span><strong>{selectedRecord.connection_name || `Connection #${selectedRecord.connection_id}`}</strong></div>
              <div><span>Query type</span><strong>{selectedRecord.query_type || "—"}</strong></div>
              <div><span>Execution time</span><strong>{formatDuration(selectedRecord.execution_time_ms)}</strong></div>
              <div><span>Rows returned</span><strong>{formatRows(selectedRecord.rows_returned)}</strong></div>
              <div><span>Status</span><strong>{selectedRecord.execution_status || "pending"}</strong></div>
              <div><span>Executed at</span><strong>{formatDate(selectedRecord.created_at)}</strong></div>
            </div>

            <div className="history-sql-heading">
              <h4>SQL statement</h4>
              <button
                type="button"
                className="history-copy-button"
                onClick={() => handleCopy(selectedRecord.original_query)}
              >
                {copied ? "Copied" : "Copy SQL"}
              </button>
            </div>
            <pre className="history-sql-code">{selectedRecord.original_query}</pre>

            {selectedRecord.error_message && (
              <div className="history-error-detail">
                <strong>Error details</strong>
                <p>{selectedRecord.error_message}</p>
              </div>
            )}
          </section>
        </div>
      )}
    </section>
  );
}

export default QueryHistory;
