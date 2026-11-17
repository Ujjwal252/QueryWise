
import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api";
import "./DatabaseConnections.css";

const INITIAL_FORM = {
  connection_name: "",
  host: "localhost",
  port: "3306",
  database_name: "",
  db_username: "",
  password: "",
  use_ssl: false,
};

function DatabaseConnections() {
  const [connections, setConnections] = useState([]);
  const [form, setForm] = useState({ ...INITIAL_FORM });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testingId, setTestingId] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [testResults, setTestResults] = useState({});

  const loadConnections = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const response = await api.getConnections();
      setConnections(response.connections || []);
    } catch (err) {
      setError(err.message || "Unable to load database connections.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConnections();
  }, [loadConnections]);

  function handleChange(event) {
    const { name, value, type, checked } = event.target;

    setForm((previous) => ({
      ...previous,
      [name]: type === "checkbox" ? checked : value,
    }));
  }

  async function handleSave(event) {
    event.preventDefault();

    setError("");
    setMessage("");

    if (
      !form.connection_name.trim() ||
      !form.host.trim() ||
      !form.database_name.trim() ||
      !form.db_username.trim() ||
      !form.password
    ) {
      setError("Please fill in all required fields.");
      return;
    }

    const port = Number(form.port);

    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      setError("Please enter a valid port number.");
      return;
    }

    try {
      setSaving(true);

      const response = await api.saveConnection({
        ...form,
        connection_name: form.connection_name.trim(),
        host: form.host.trim(),
        port,
        database_name: form.database_name.trim(),
        db_username: form.db_username.trim(),
      });

      setMessage(response.message || "Connection saved successfully.");
      setForm({ ...INITIAL_FORM });

      await loadConnections();
    } catch (err) {
      setError(err.message || "Unable to save the connection.");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest(connectionId) {
    setError("");
    setMessage("");
    setTestingId(connectionId);

    try {
      const response = await api.testConnection(connectionId);

      setTestResults((previous) => ({
        ...previous,
        [connectionId]: {
          success: true,
          message: response.message || "Connection successful.",
        },
      }));
    } catch (err) {
      setTestResults((previous) => ({
        ...previous,
        [connectionId]: {
          success: false,
          message: err.message || "Connection test failed.",
        },
      }));
    } finally {
      setTestingId(null);
    }
  }

  async function handleDelete(connectionId) {
    const confirmed = window.confirm(
      "Are you sure you want to delete this database connection?"
    );

    if (!confirmed) return;

    setError("");
    setMessage("");

    try {
      const response = await api.deleteConnection(connectionId);

      setMessage(response.message || "Connection deleted successfully.");

      setTestResults((previous) => {
        const updated = { ...previous };
        delete updated[connectionId];
        return updated;
      });

      await loadConnections();
    } catch (err) {
      setError(err.message || "Unable to delete the connection.");
    }
  }

  function formatDate(dateValue) {
    if (!dateValue) return "Not available";

    const date = new Date(dateValue);

    if (Number.isNaN(date.getTime())) return "Not available";

    return date.toLocaleDateString();
  }

  return (
    <div className="connections-page">
      <div className="connections-header">
        <div>
          <h2>Manage Database Connections</h2>
          <p className="connections-description">
            Connect your MySQL databases to analyze, optimize, and
            evaluate your SQL queries.
          </p>
        </div>
      </div>

      {error && (
        <div className="connection-alert error" role="alert">
          {error}
        </div>
      )}

      {message && (
        <div className="connection-alert success" role="status">
          {message}
        </div>
      )}

      <section className="connection-panel">
        <div className="connection-panel-heading">
          <div>
            <h3>Add New Database Connection</h3>
            <p>Enter your MySQL database details below.</p>
          </div>
        </div>

        <form className="connection-form" onSubmit={handleSave}>
          <div className="connection-form-grid">
            <label>
              Connection Name *
              <input
                type="text"
                name="connection_name"
                placeholder="e.g. My Test Database"
                value={form.connection_name}
                onChange={handleChange}
                maxLength={100}
                required
              />
            </label>

            <label>
              Host *
              <input
                type="text"
                name="host"
                placeholder="localhost or 127.0.0.1"
                value={form.host}
                onChange={handleChange}
                required
              />
            </label>

            <label>
              Port *
              <input
                type="number"
                name="port"
                min="1"
                max="65535"
                value={form.port}
                onChange={handleChange}
                required
              />
            </label>

            <label>
              Database Name *
              <input
                type="text"
                name="database_name"
                placeholder="Enter database name"
                value={form.database_name}
                onChange={handleChange}
                required
              />
            </label>

            <label>
              Database Username *
              <input
                type="text"
                name="db_username"
                placeholder="Enter MySQL username"
                value={form.db_username}
                onChange={handleChange}
                autoComplete="off"
                required
              />
            </label>

            <label>
              Database Password *
              <input
                type="password"
                name="password"
                placeholder="Enter MySQL password"
                value={form.password}
                onChange={handleChange}
                autoComplete="new-password"
                required
              />
            </label>
          </div>

          <label className="ssl-option">
            <input
              type="checkbox"
              name="use_ssl"
              checked={form.use_ssl}
              onChange={handleChange}
            />
            Enable SSL connection
          </label>

          <div className="connection-form-actions">
            <button type="submit" disabled={saving}>
              {saving ? "Saving..." : "+ Add Connection"}
            </button>
          </div>
        </form>
      </section>

      <div className="connections-summary">
        <div>
          <h3>Saved Connections</h3>
          <p>
            {connections.length} database connection
            {connections.length !== 1 ? "s" : ""} configured
          </p>
        </div>

        <div className="connections-summary-icon">▤</div>
      </div>

      {loading ? (
        <div className="connections-empty">
          Loading database connections...
        </div>
      ) : connections.length === 0 ? (
        <div className="connections-empty">
          <div className="empty-icon">▤</div>
          <h3>No Database Connections Yet</h3>
          <p>
            Add your first MySQL database connection using the form above.
          </p>
        </div>
      ) : (
        <div className="connection-list">
          {connections.map((connection) => {
            const result = testResults[connection.connection_id];

            return (
              <article
                className="connection-card"
                key={connection.connection_id}
              >
                <div className="connection-card-header">
                  <div className="database-icon">▤</div>

                  <div className="connection-card-title">
                    <h4>{connection.connection_name}</h4>
                    <span className="connection-type">MySQL</span>
                  </div>
                </div>

                <div className="connection-details">
                  <p>
                    <span>Host</span>
                    <strong>
                      {connection.host}:{connection.port}
                    </strong>
                  </p>

                  <p>
                    <span>Database</span>
                    <strong>{connection.database_name}</strong>
                  </p>

                  <p>
                    <span>Username</span>
                    <strong>{connection.db_username}</strong>
                  </p>

                  <p>
                    <span>SSL</span>
                    <strong>
                      {connection.use_ssl ? "Enabled" : "Disabled"}
                    </strong>
                  </p>

                  <p>
                    <span>Created</span>
                    <strong>{formatDate(connection.created_at)}</strong>
                  </p>
                </div>

                {result && (
                  <div
                    className={`connection-test-result ${
                      result.success ? "test-success" : "test-failure"
                    }`}
                  >
                    {result.message}
                  </div>
                )}

                <div className="connection-card-actions">
                  <button
                    type="button"
                    className="test-button"
                    disabled={testingId === connection.connection_id}
                    onClick={() => handleTest(connection.connection_id)}
                  >
                    {testingId === connection.connection_id
                      ? "Testing..."
                      : "Test Connection"}
                  </button>

                  <button
                    type="button"
                    className="delete-button"
                    onClick={() =>
                      handleDelete(connection.connection_id)
                    }
                  >
                    Delete
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default DatabaseConnections;
