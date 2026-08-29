// App JS - Dynamic Dashboard Logic
document.addEventListener("DOMContentLoaded", () => {
    loadOverview();
    loadSignals();
    loadPaperTrading();
    initCharts();
});

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

    event.currentTarget.classList.add('active');
    document.getElementById(tabId).classList.add('active');
}

async function loadOverview() {
    try {
        const res = await fetch('/api/overview');
        const data = await res.json();

        // Currency Strength Grid
        const grid = document.getElementById('currency-strength-grid');
        grid.innerHTML = '';
        for (const [curr, score] of Object.entries(data.currency_strength || {})) {
            const isPos = score >= 0;
            grid.innerHTML += `
                <div class="glass-card">
                    <div class="metric-title">${curr}</div>
                    <div class="metric-value ${isPos ? 'positive' : 'negative'}">${score > 0 ? '+' : ''}${score.toFixed(2)}</div>
                </div>
            `;
        }

        // Market Table
        const tbody = document.getElementById('market-monitor-body');
        tbody.innerHTML = '';
        (data.tracked_assets || []).forEach(item => {
            const isLong = item.direction === 'LONG';
            tbody.innerHTML += `
                <tr>
                    <td style="font-weight: 600;">${item.symbol}</td>
                    <td>${item.price.toFixed(5)}</td>
                    <td><span class="direction-tag ${isLong ? 'long' : 'short'}">${item.direction}</span></td>
                    <td>${item.score}/100</td>
                    <td>${item.rsi}</td>
                    <td>${item.adx}</td>
                    <td style="color: var(--text-muted);">${item.setup}</td>
                </tr>
            `;
        });
    } catch (err) {
        console.error("Error loading overview:", err);
    }
}

async function loadSignals() {
    try {
        const res = await fetch('/api/signals');
        const data = await res.json();
        const container = document.getElementById('signals-container');
        container.innerHTML = '';

        (data.signals || []).forEach(sig => {
            const isLong = sig.direction === 'LONG';
            const reasoningJson = JSON.stringify(sig.reasoning_object || {}).replace(/"/g, '&quot;');

            container.innerHTML += `
                <div class="signal-card">
                    <div class="signal-header">
                        <div>
                            <span style="font-size: 1.2rem; font-weight: 700;">${sig.symbol_name}</span>
                            <span class="direction-tag ${isLong ? 'long' : 'short'}" style="margin-left: 8px;">${sig.direction}</span>
                        </div>
                        <span style="font-weight: 700; color: var(--accent-emerald);">Score: ${sig.opportunity_score}</span>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 16px;">
                        <div>Entry: <strong style="color: white;">${sig.entry_price}</strong></div>
                        <div>SL: <strong style="color: var(--accent-rose);">${sig.stop_loss}</strong></div>
                        <div>Target 1: <strong style="color: var(--accent-emerald);">${sig.take_profit_1}</strong></div>
                        <div>R:R Ratio: <strong style="color: white;">1:${sig.risk_reward}</strong></div>
                    </div>
                    <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 16px; font-style: italic;">
                        "${sig.llm_reasoning}"
                    </p>
                    <button class="btn-primary" style="width: 100%; font-size: 0.85rem;" onclick='openModal("${sig.symbol_name}", "${sig.direction}", ${reasoningJson})'>
                        ❓ WHY THIS TRADE? (Detailed Rationale)
                    </button>
                </div>
            `;
        });
    } catch (err) {
        console.error("Error loading signals:", err);
    }
}

async function loadPaperTrading() {
    try {
        const res = await fetch('/api/paper-trading');
        const data = await res.json();
        document.getElementById('pt-balance').innerText = `$${data.current_balance.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
        document.getElementById('pt-pnl').innerText = `${data.net_pnl >= 0 ? '+' : ''}$${data.net_pnl.toFixed(2)}`;
        document.getElementById('pt-winrate').innerText = `${data.win_rate_pct}%`;
        document.getElementById('pt-profit-factor').innerText = data.profit_factor;
    } catch (err) {
        console.error("Error loading paper trading:", err);
    }
}

function openModal(symbol, direction, reasoning) {
    document.getElementById('modal-title').innerText = `❓ WHY THIS TRADE? — ${symbol} (${direction})`;
    
    let html = `<p style="margin-bottom: 12px; font-weight: 600; color: white;">${reasoning.summary || ''}</p>`;
    html += `<h5 style="color: var(--accent-emerald); margin-top: 12px;">✅ Supporting Evidence:</h5><ul>`;
    (reasoning.supporting_factors || []).forEach(f => {
        html += `<li style="margin-left: 20px;">${f}</li>`;
    });
    html += `</ul>`;

    if ((reasoning.contradiction_factors || []).length > 0) {
        html += `<h5 style="color: var(--accent-rose); margin-top: 12px;">⚠️ Contradicting Evidence:</h5><ul>`;
        (reasoning.contradiction_factors || []).forEach(c => {
            html += `<li style="margin-left: 20px;">${c}</li>`;
        });
        html += `</ul>`;
    }

    html += `<h5 style="color: var(--accent-cyan); margin-top: 12px;">🛑 Invalidation Logic:</h5>`;
    html += `<p style="font-size: 0.85rem; color: var(--text-muted);">${(reasoning.invalidation_logic || []).join(', ')}</p>`;

    document.getElementById('modal-body').innerHTML = html;
    document.getElementById('rationale-modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('rationale-modal').style.display = 'none';
}

async function testTelegram() {
    const token = document.getElementById('tg-token').value;
    const chatId = document.getElementById('tg-chatid').value;
    const output = document.getElementById('tg-status-output');

    output.innerText = "Testing Telegram connection...";
    output.style.color = "var(--text-secondary)";

    try {
        const res = await fetch('/api/config/telegram/test', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({bot_token: token, chat_id: chatId})
        });
        const data = await res.json();
        if (data.status === 'CONNECTED') {
            output.innerText = "✅ Connection Successful! Test message sent to Telegram.";
            output.style.color = "var(--accent-emerald)";
        } else {
            output.innerText = `❌ Connection Failed: ${data.message}`;
            output.style.color = "var(--accent-rose)";
        }
    } catch (err) {
        output.innerText = `❌ Error: ${err}`;
        output.style.color = "var(--accent-rose)";
    }
}

async function triggerScan() {
    try {
        const res = await fetch('/api/scan/trigger', {method: 'POST'});
        const data = await res.json();
        alert(data.message);
        loadOverview();
        loadSignals();
    } catch (err) {
        alert("Scan trigger error: " + err);
    }
}

async function saveLLMConfig() {
    const deepseekKey = document.getElementById('llm-deepseek-key').value;
    const azureKey = document.getElementById('llm-azure-key').value;
    const azureEndpoint = document.getElementById('llm-azure-endpoint').value;
    const azureDeployment = document.getElementById('llm-azure-deployment').value;
    const geminiKey = document.getElementById('llm-gemini-key').value;
    const openaiKey = document.getElementById('llm-openai-key').value;
    const output = document.getElementById('llm-status-output');

    output.innerText = "Saving LLM credentials...";
    output.style.color = "var(--text-secondary)";

    try {
        const res = await fetch('/api/config/llm/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                deepseek_key: deepseekKey,
                azure_key: azureKey,
                azure_endpoint: azureEndpoint,
                azure_deployment: azureDeployment,
                gemini_key: geminiKey,
                openai_key: openaiKey
            })
        });
        const data = await res.json();
        output.innerText = "✅ " + data.message;
        output.style.color = "var(--accent-emerald)";
    } catch (err) {
        output.innerText = "❌ Error saving LLM config: " + err;
        output.style.color = "var(--accent-rose)";
    }
}

async function testLLMConnection() {
    const output = document.getElementById('llm-status-output');
    output.innerText = "Evaluating multi-provider LLM routing...";
    output.style.color = "var(--text-secondary)";

    try {
        const res = await fetch('/api/config/llm/test', {method: 'POST'});
        const data = await res.json();
        if (data.status === 'SUCCESS') {
            output.innerText = `✅ LLM Test Passed! Active Provider: ${data.active_provider}. Response: "${data.reasoning}"`;
            output.style.color = "var(--accent-emerald)";
        } else {
            output.innerText = `⚠️ LLM Test Result: ${data.message}`;
            output.style.color = "var(--accent-amber)";
        }
    } catch (err) {
        output.innerText = "❌ Error testing LLM: " + err;
        output.style.color = "var(--accent-rose)";
    }
}

function initCharts() {
    // Equity Chart
    const ctxEquity = document.getElementById('equityChart').getContext('2d');
    new Chart(ctxEquity, {
        type: 'line',
        data: {
            labels: ['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5', 'Day 6'],
            datasets: [{
                label: 'Simulated Equity ($)',
                data: [10000, 10150, 10080, 10320, 10290, 10540],
                borderColor: '#10B981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: 'rgba(255,255,255,0.05)' } },
                y: { grid: { color: 'rgba(255,255,255,0.05)' } }
            }
        }
    });

    // Funnel Chart
    const ctxFunnel = document.getElementById('funnelChart').getContext('2d');
    new Chart(ctxFunnel, {
        type: 'bar',
        data: {
            labels: ['Ticks', 'Valid Data', 'Technical', 'ML Prob', 'Risk R:R', 'Approved', 'Alerted'],
            datasets: [{
                label: 'Candidate Count',
                data: [100, 98, 45, 18, 8, 4, 4],
                backgroundColor: '#06B6D4',
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: 'rgba(255,255,255,0.05)' } },
                y: { grid: { color: 'rgba(255,255,255,0.05)' } }
            }
        }
    });
}
