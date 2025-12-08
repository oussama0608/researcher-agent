import React, { useMemo, useState } from "react";
import { apiBase, runAgent } from "./api";

const initialForm = {
  company: "Acme Corp",
  url: "",
  provider: "openai",
  model: "gpt-4o-mini",
};

function StatusPill({ status }) {
  const palette = {
    idle: { text: "Idle", className: "pill pill-neutral" },
    running: { text: "Researching…", className: "pill pill-active" },
    ready: { text: "Ready for approval", className: "pill pill-ready" },
    sent: { text: "Mock sent ✓", className: "pill pill-sent" },
  };
  const data = palette[status] || palette.idle;
  return <span className={data.className}>{data.text}</span>;
}

function DownloadIcon() {
  return (
    <svg className="download-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function App() {
  const [form, setForm] = useState(initialForm);
  const [logLines, setLogLines] = useState([]);
  const [summary, setSummary] = useState("");
  const [emailDraft, setEmailDraft] = useState("");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [sendMessage, setSendMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const heroTitle = useMemo(
    () => `Cold Outreach Researcher · ${form.provider === "openai" ? "OpenAI" : "Anthropic"}`,
    [form.provider],
  );

  const handleChange = (evt) => {
    const { name, value } = evt.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (evt) => {
    evt.preventDefault();
    setIsSubmitting(true);
    setError("");
    setStatus("running");
    setSendMessage("");
    setSummary("");
    setEmailDraft("");
    setLogLines([]);

    try {
      const result = await runAgent(form);
      setLogLines(result.log || []);
      setSummary(result.summary || "");
      setEmailDraft(result.email_draft || "");
      setStatus("ready");
    } catch (err) {
      setError(err.message || "Failed to run agent.");
      setStatus("idle");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSend = () => {
    if (!emailDraft.trim()) {
      setSendMessage("Nothing to send—please run the agent first.");
      return;
    }
    setSendMessage("Mock send complete. (Hook your email API here.)");
    setStatus("sent");
  };

  const handleDownload = () => {
    if (!summary && !emailDraft) {
      return;
    }
    const content = `# Research Results for ${form.company}
Generated: ${new Date().toLocaleString()}

## Summary
${summary || "No summary available."}

## Email Draft
${emailDraft || "No email draft available."}
`;
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${form.company.replace(/\s+/g, "_")}_outreach.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="page">
      <div className="grid">
        <header className="hero">
          <div>
            <p className="eyebrow">LangGraph · Tavily · BeautifulSoup</p>
            <h1>{heroTitle}</h1>
            <p className="lede">
              Research a company, scrape their site, and draft a personalized cold email. Review and approve before
              sending.
            </p>
            <div className="badges">
              <StatusPill status={status} />
              <span className="pill pill-ghost">API {apiBase}</span>
            </div>
          </div>
          <div className="hero-card">
            <p className="hint">Safety</p>
            <p className="hero-callout">Human-in-the-loop approval step before any send.</p>
          </div>
        </header>

        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="hint">Input</p>
              <h2>Lead details</h2>
            </div>
            <button className="ghost-btn" type="button" onClick={() => setForm(initialForm)}>
              Reset
            </button>
          </div>
          <form className="form" onSubmit={handleSubmit}>
            <label className="field">
              <span>Company name</span>
              <input
                name="company"
                value={form.company}
                onChange={handleChange}
                placeholder="Acme Corp"
                required
              />
            </label>
            <label className="field">
              <span>Homepage (optional)</span>
              <input
                name="url"
                value={form.url}
                onChange={handleChange}
                placeholder="https://www.acme.com"
                type="url"
              />
            </label>
            <div className="field-row">
              <label className="field">
                <span>Provider</span>
                <select name="provider" value={form.provider} onChange={handleChange}>
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                </select>
              </label>
              <label className="field">
                <span>Model</span>
                <input name="model" value={form.model} onChange={handleChange} />
              </label>
            </div>
            <button type="submit" className="primary-btn" disabled={isSubmitting}>
              {isSubmitting ? "Running..." : "Run research + draft"}
            </button>
            {error && <p className="error">{error}</p>}
          </form>
        </section>

        <section className="panel two-col">
          <div className="col">
            <div className="panel-header">
              <div>
                <p className="hint">Trace</p>
                <h2>Execution log</h2>
              </div>
            </div>
            <div className="log-box">
              {logLines.length === 0 ? (
                <p className="muted">Waiting to run…</p>
              ) : (
                logLines.map((line, idx) => (
                  <div key={idx} className="log-line">
                    {line}
                  </div>
                ))
              )}
            </div>
          </div>
          <div className="col">
            <div className="panel-header">
              <div>
                <p className="hint">Output</p>
                <h2>Summary & Email</h2>
              </div>
              <StatusPill status={status} />
            </div>
            <div className="summary">
              <h3>Summary</h3>
              <p className="muted">{summary || "Will populate after the run."}</p>
            </div>
            <div className="email">
              <div className="panel-header">
                <h3>Email draft</h3>
              </div>
              <textarea
                value={emailDraft}
                onChange={(evt) => setEmailDraft(evt.target.value)}
                placeholder="Run the agent to draft an email..."
                rows={12}
              />
              <div className="action-row">
                <button type="button" className="primary-btn" onClick={handleSend} disabled={!emailDraft}>
                  Approve & mock send
                </button>
                <button
                  type="button"
                  className="secondary-btn"
                  onClick={handleDownload}
                  disabled={!summary && !emailDraft}
                >
                  <DownloadIcon />
                  Download
                </button>
                {sendMessage && <p className="success-message">✓ {sendMessage}</p>}
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

export default App;
