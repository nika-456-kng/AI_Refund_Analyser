import React, { useState } from 'react';
import './App.css';

function App() {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!message) return;
    setLoading(true);
    setResult(null);

    try {
      const response = await fetch('http://127.0.0.1:8000/api/process-refund', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message }),
      });
      const data = await response.json();
      setResult(data);
    } catch (error) {
      alert("Error contacting the AI Backend server.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>🛡️ Enterprise AI Refund Center</h1>
        <p>Multi-Agent Orchestration & Vector Search Portal</p>
      </header>

      <main className="main-content">
        <div className="card input-card">
          <h2>📥 Process Customer Request</h2>
          <form onSubmit={handleSubmit}>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="e.g., I need a refund for order ORD12345, it arrived shattered!"
              rows="5"
            />
            <button type="submit" disabled={loading}>
              {loading ? '🧠 Processing Data...' : 'Execute Agent Pipeline'}
            </button>
          </form>

          <div className="scenarios-box">
            <h3>📋 Test Scenarios Provided:</h3>
            <ul>
              <li><strong>ORD12345:</strong> Bought 5 days ago (Electronics) ➔ Full Refund</li>
              <li><strong>ORD67890:</strong> Bought 45 days ago (Clothing) ➔ 50% Partial Store Credit</li>
              <li><strong>ORD55555:</strong> Digital Product ➔ Auto-Rejected instantly</li>
            </ul>
          </div>
        </div>

        {result && (
          <div className="results-container">
            <div className="card variables-card">
              <h2>👁️ Internal Workspace variables</h2>
              <div className="metric">
                <strong>Extracted Tracking ID:</strong> <span>{result.order_id || 'None'}</span>
              </div>
              {result.order_data && (
                <div className="metric-block">
                  <strong>Database Lookup Match:</strong>
                  <pre>{JSON.stringify(result.order_data, null, 2)}</pre>
                </div>
              )}
              {result.policy_data && (
                <div className="metric-block bg-blue">
                  <strong>FAISS Document Retrieval Match:</strong>
                  <p><em>"{result.policy_data}"</em></p>
                </div>
              )}
            </div>

            <div className="card email-card">
              <h2>📬 Automated Customer Deliverable</h2>
              <pre className="email-preview">{result.final_decision}</pre>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;