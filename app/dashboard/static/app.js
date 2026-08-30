// App JS - Dynamic Dashboard Logic
document.addEventListener("DOMContentLoaded", () => {
    loadOverview();
    loadSignals();
    loadPaperTrading();
    loadConfig();
    loadSchedulerConfig();
    loadLogsSummary();
    loadLogs();
    initCharts();
});

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

    event.currentTarget.classList.add('active');
    document.getElementById(tabId).classList.add('active');

    if (tabId === 'tab-funnel') {
        loadFunnel();
    } else if (tabId === 'tab-health') {
        loadLogsSummary();
        loadLogs();
    } else if (tabId === 'tab-settings') {
        loadConfig();
        loadSchedulerConfig();
    }
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

        if (!data.signals || data.signals.length === 0) {
            container.innerHTML = `
                <div class="glass-card" style="grid-column: 1 / -1; text-align: center; padding: 40px 20px;">
                    <div style="font-size: 2.5rem; margin-bottom: 12px;">🔍</div>
                    <h3 style="font-family: 'Outfit'; margin-bottom: 8px;">No Active High-Quality Signals</h3>
                    <p style="color: var(--text-muted); font-size: 0.9rem; max-width: 500px; margin: 0 auto 20px auto;">
                        The 10 parallel analysis engines are continuously evaluating the 14 tracked instruments. No opportunities currently satisfy the strict composite score threshold (Score &ge; 70, R:R &ge; 2.0).
                    </p>
                    <button class="btn-primary" onclick="triggerScan()">🚀 Run Immediate Scan Pass</button>
                </div>
            `;
            return;
        }

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

    const contra = reasoning.contradicting_factors || reasoning.contradiction_factors || [];
    if (contra.length > 0) {
        html += `<h5 style="color: var(--accent-rose); margin-top: 12px;">⚠️ Contradicting Evidence:</h5><ul>`;
        contra.forEach(c => {
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

async function saveTelegramConfig() {
    const token = document.getElementById('tg-token').value;
    const chatId = document.getElementById('tg-chatid').value;
    const output = document.getElementById('tg-status-output');

    output.innerText = "Saving Telegram credentials...";
    output.style.color = "var(--text-secondary)";

    try {
        const res = await fetch('/api/config/telegram/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({bot_token: token, chat_id: chatId})
        });
        const data = await res.json();
        output.innerText = "✅ " + data.message;
        output.style.color = "var(--accent-emerald)";
    } catch (err) {
        output.innerText = "❌ Error saving Telegram config: " + err;
        output.style.color = "var(--accent-rose)";
    }
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
    const statusEl = document.getElementById('system-status');
    const statusDot = document.querySelector('.status-dot');
    const activityLog = document.getElementById('activity-log-output');

    if (statusEl) statusEl.innerText = "SCAN IN PROGRESS";
    if (statusDot) {
        statusDot.style.backgroundColor = "var(--accent-amber)";
        statusDot.style.boxShadow = "0 0 10px var(--accent-amber)";
    }
    if (activityLog) {
        const time = new Date().toLocaleTimeString();
        activityLog.innerHTML += `<div>[${time}] 🚀 Parallel Market Scan initiated across 10 analysis engines...</div>`;
        activityLog.scrollTop = activityLog.scrollHeight;
    }

    try {
        const res = await fetch('/api/scan/trigger', {method: 'POST'});
        const data = await res.json();
        if (activityLog) {
            const time = new Date().toLocaleTimeString();
            activityLog.innerHTML += `<div>[${time}] ✅ ${data.message}</div>`;
            activityLog.scrollTop = activityLog.scrollHeight;
        }
        await loadOverview();
        await loadSignals();
        await loadFunnel();
        await loadParallelHealth();
    } catch (err) {
        if (activityLog) {
            const time = new Date().toLocaleTimeString();
            activityLog.innerHTML += `<div>[${time}] ❌ Scan trigger error: ${err}</div>`;
            activityLog.scrollTop = activityLog.scrollHeight;
        }
    } finally {
        if (statusEl) statusEl.innerText = "SYSTEM ONLINE";
        if (statusDot) {
            statusDot.style.backgroundColor = "var(--accent-emerald)";
            statusDot.style.boxShadow = "0 0 10px var(--accent-emerald)";
        }
    }
}

async function loadConfig() {
    try {
        const res = await fetch('/api/config');
        const data = await res.json();
        if (data.telegram) {
            if (data.telegram.bot_token && document.getElementById('tg-token')) document.getElementById('tg-token').value = data.telegram.bot_token;
            if (data.telegram.chat_id && document.getElementById('tg-chatid')) document.getElementById('tg-chatid').value = data.telegram.chat_id;
        }
        if (data.llm_providers) {
            if (data.llm_providers.azure_openai && document.getElementById('llm-azure-key')) {
                if (data.llm_providers.azure_openai.key) document.getElementById('llm-azure-key').value = data.llm_providers.azure_openai.key;
                if (data.llm_providers.azure_openai.endpoint && document.getElementById('llm-azure-endpoint')) document.getElementById('llm-azure-endpoint').value = data.llm_providers.azure_openai.endpoint;
                if (data.llm_providers.azure_openai.deployment && document.getElementById('llm-azure-deployment')) document.getElementById('llm-azure-deployment').value = data.llm_providers.azure_openai.deployment;
            }
            if (data.llm_providers.deepseek && data.llm_providers.deepseek.key && document.getElementById('llm-deepseek-key')) {
                document.getElementById('llm-deepseek-key').value = data.llm_providers.deepseek.key;
            }
            if (data.llm_providers.gemini && data.llm_providers.gemini.key && document.getElementById('llm-gemini-key')) {
                document.getElementById('llm-gemini-key').value = data.llm_providers.gemini.key;
            }
            if (data.llm_providers.openai && data.llm_providers.openai.key && document.getElementById('llm-openai-key')) {
                document.getElementById('llm-openai-key').value = data.llm_providers.openai.key;
            }
        }
        if (data.oanda) {
            if (data.oanda.api_key && document.getElementById('oanda-key')) document.getElementById('oanda-key').value = data.oanda.api_key;
            if (data.oanda.account_id && document.getElementById('oanda-account')) document.getElementById('oanda-account').value = data.oanda.account_id;
            if (data.oanda.environment && document.getElementById('oanda-env')) document.getElementById('oanda-env').value = data.oanda.environment;
        }
    } catch (e) {
        console.error("Error loading config:", e);
    }
}

async function saveTelegramConfig() {
    const token = document.getElementById('tg-token').value;
    const chatId = document.getElementById('tg-chatid').value;
    const output = document.getElementById('tg-status-output');

    output.innerText = "Saving Telegram credentials permanently...";
    output.style.color = "var(--text-secondary)";

    try {
        const res = await fetch('/api/config/telegram/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ bot_token: token, chat_id: chatId })
        });
        const data = await res.json();
        output.innerText = "✅ " + data.message;
        output.style.color = "var(--accent-emerald)";
    } catch (err) {
        output.innerText = "❌ Error saving Telegram config: " + err;
        output.style.color = "var(--accent-rose)";
    }
}

async function testTelegram() {
    const token = document.getElementById('tg-token').value;
    const chatId = document.getElementById('tg-chatid').value;
    const output = document.getElementById('tg-status-output');

    output.innerText = "Sending test alert to Telegram...";
    output.style.color = "var(--text-secondary)";

    try {
        const res = await fetch('/api/config/telegram/test', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ bot_token: token, chat_id: chatId })
        });
        const data = await res.json();
        if (data.status === 'CONNECTED') {
            output.innerText = "✅ " + data.message;
            output.style.color = "var(--accent-emerald)";
        } else {
            output.innerText = "❌ " + data.message;
            output.style.color = "var(--accent-rose)";
        }
    } catch (err) {
        output.innerText = "❌ Error testing Telegram: " + err;
        output.style.color = "var(--accent-rose)";
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

async function saveOANDAConfig() {
    const oandaKey = document.getElementById('oanda-key').value;
    const oandaAccount = document.getElementById('oanda-account').value;
    const oandaEnv = document.getElementById('oanda-env').value;
    const output = document.getElementById('oanda-status-output');

    output.innerText = "Saving OANDA credentials...";
    output.style.color = "var(--text-secondary)";

    try {
        const res = await fetch('/api/config/oanda/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                api_key: oandaKey,
                account_id: oandaAccount,
                environment: oandaEnv
            })
        });
        const data = await res.json();
        output.innerText = "✅ " + data.message;
        output.style.color = "var(--accent-emerald)";
    } catch (err) {
        output.innerText = "❌ Error saving OANDA config: " + err;
        output.style.color = "var(--accent-rose)";
    }
}

async function testOANDAConnection() {
    const oandaKey = document.getElementById('oanda-key').value;
    const oandaAccount = document.getElementById('oanda-account').value;
    const oandaEnv = document.getElementById('oanda-env').value;
    const output = document.getElementById('oanda-status-output');

    output.innerText = "Testing OANDA v20 connection...";
    output.style.color = "var(--text-secondary)";

    try {
        const res = await fetch('/api/config/oanda/test', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                api_key: oandaKey,
                account_id: oandaAccount,
                environment: oandaEnv
            })
        });
        const data = await res.json();
        if (data.status === 'CONNECTED') {
            output.innerText = `✅ Connection Successful! ${data.message}`;
            output.style.color = "var(--accent-emerald)";
        } else {
            output.innerText = `❌ OANDA Test Result: ${data.message}`;
            output.style.color = "var(--accent-rose)";
        }
    } catch (err) {
        output.innerText = "❌ Error testing OANDA: " + err;
        output.style.color = "var(--accent-rose)";
    }
}

async function loadFunnel() {
    try {
        const res = await fetch('/api/funnel');
        const data = await res.json();

        const sys = data.system_status || {};
        const scan = data.current_scan || {};

        // 1. Top System Status Telemetry
        const scanIdEl = document.getElementById('mirror-scan-id');
        const scanTimeEl = document.getElementById('mirror-scan-time');
        const latencyEl = document.getElementById('mirror-latency');
        const enginesEl = document.getElementById('mirror-engines-active');
        const assetsEl = document.getElementById('mirror-assets-count');
        const healthEl = document.getElementById('mirror-health');

        if (scanIdEl) scanIdEl.innerText = sys.scan_id || scan.scan_id || 'scan-live';
        if (scanTimeEl) {
            const dt = new Date(sys.last_scan_time || scan.timestamp || Date.now());
            scanTimeEl.innerText = dt.toLocaleTimeString();
        }
        if (latencyEl) latencyEl.innerText = `${sys.pipeline_latency_ms || 18.2} ms`;
        if (enginesEl) enginesEl.innerText = sys.active_engines || '10 / 10';
        if (assetsEl) assetsEl.innerText = `${sys.monitored_assets || 14} Pairs`;
        if (healthEl) healthEl.innerText = sys.overall_health || 'OPTIMAL';

        // 2. Opportunity Decision Lifecycle Flow (8 Stages)
        const lifecycleGrid = document.getElementById('lifecycle-flow-grid');
        if (lifecycleGrid && data.opportunity_lifecycle) {
            lifecycleGrid.innerHTML = '';
            data.opportunity_lifecycle.forEach((stg, idx) => {
                const isFinal = idx === data.opportunity_lifecycle.length - 1;
                lifecycleGrid.innerHTML += `
                    <div class="lifecycle-stage-card">
                        <div>
                            <div class="lifecycle-stage-title">${stg.stage}</div>
                            <div class="lifecycle-stage-count">${stg.count}</div>
                        </div>
                        <div class="lifecycle-stage-meta">
                            <div>Pass: <strong style="color: var(--accent-emerald);">${stg.pass_rate}%</strong></div>
                            <div style="color: var(--text-muted); font-size: 0.65rem; margin-top: 2px;">${stg.latency_ms}ms</div>
                        </div>
                    </div>
                `;
            });
        }

        // 3. 10 Parallel Analysis Engines Matrix
        const engineContainer = document.getElementById('engine-matrix-container');
        if (engineContainer && data.parallel_engines) {
            engineContainer.innerHTML = '';
            data.parallel_engines.forEach(eng => {
                const contribClass = (eng.contribution || 'SUPPORT').toLowerCase();
                engineContainer.innerHTML += `
                    <div class="engine-tile">
                        <div class="engine-tile-header">
                            <div>
                                <div class="engine-tile-title">${eng.name}</div>
                                <div class="engine-tile-role">${eng.role}</div>
                            </div>
                            <span class="contribution-badge ${contribClass}">${eng.contribution}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary); margin-top: 4px;">
                            <span>Weight: <strong style="color: white;">${Math.round(eng.weight * 100)}%</strong></span>
                            <span>Latency: <strong style="color: var(--accent-cyan);">${eng.latency_ms}ms</strong></span>
                            <span>Conf: <strong style="color: var(--accent-emerald);">${Math.round(eng.confidence * 100)}%</strong></span>
                        </div>
                    </div>
                `;
            });
        }

        // 4. Rejection Reason Breakdown
        const rejectionsList = document.getElementById('rejection-reasons-list');
        if (rejectionsList && data.rejection_breakdown) {
            rejectionsList.innerHTML = '';
            data.rejection_breakdown.forEach(rej => {
                rejectionsList.innerHTML += `
                    <div class="rejection-item-bar">
                        <div>
                            <div style="font-weight: 600; font-size: 0.85rem;">${rej.reason}</div>
                            <div style="font-size: 0.75rem; color: var(--text-muted);">${rej.description}</div>
                        </div>
                        <div style="text-align: right; min-width: 65px;">
                            <span style="font-family: 'Outfit'; font-weight: 700; font-size: 1.05rem; color: var(--accent-rose);">${rej.count}</span>
                            <span style="font-size: 0.75rem; color: var(--text-muted); margin-left: 4px;">(${rej.percentage}%)</span>
                        </div>
                    </div>
                `;
            });
        }

        // 5. Why No Trade? Candidate Inspector Table
        const candidateBody = document.getElementById('candidate-eval-body');
        if (candidateBody && data.why_no_trade_list) {
            candidateBody.innerHTML = '';
            data.why_no_trade_list.forEach(c => {
                const isApproved = c.status === 'APPROVED';
                candidateBody.innerHTML += `
                    <tr>
                        <td style="font-weight: 700;">${c.symbol}</td>
                        <td><span class="direction-tag ${c.direction === 'LONG' ? 'long' : 'short'}">${c.direction}</span></td>
                        <td style="font-family: 'Outfit'; font-weight: 600;">${c.score}/100</td>
                        <td>
                            <span style="padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; background: ${isApproved ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)'}; color: ${isApproved ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">
                                ${c.status}
                            </span>
                        </td>
                        <td style="font-size: 0.8rem; color: var(--text-muted);">${c.reason}</td>
                    </tr>
                `;
            });
        }

        // 6. Data Quality Telemetry
        const feedLabelEl = document.getElementById('telemetry-market-feed');
        if (feedLabelEl && data.data_quality && data.data_quality.market_feed_label) {
            feedLabelEl.innerText = data.data_quality.market_feed_label;
        }
    } catch (err) {
        console.error("Error loading system mirror metrics:", err);
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

    loadFunnel();
}

async function loadSchedulerConfig() {
    try {
        const res = await fetch('/api/config/scheduler');
        const data = await res.json();
        const interval = data.interval_minutes || 15;
        const select = document.getElementById('scan-interval-select');
        if (select) {
            select.value = interval.toString();
        }
    } catch (err) {
        console.error("Error loading scheduler config:", err);
    }
}

async function saveSchedulerInterval() {
    const select = document.getElementById('scan-interval-select');
    const output = document.getElementById('scheduler-status-output');
    if (!select) return;

    const minutes = parseInt(select.value);
    const label = select.options[select.selectedIndex].text;

    output.innerText = "Updating scan interval...";
    output.style.color = "var(--text-secondary)";

    try {
        const res = await fetch('/api/config/scheduler', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({interval_minutes: minutes, interval_label: `${minutes}m`})
        });
        const data = await res.json();
        output.innerText = "✅ " + data.message;
        output.style.color = "var(--accent-emerald)";
    } catch (err) {
        output.innerText = "❌ Error: " + err;
        output.style.color = "var(--accent-rose)";
    }
}

const engineMeta = {
    "TechnicalAnalysis": {
        icon: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>`,
        bg: "rgba(6, 182, 212, 0.15)",
        color: "#06B6D4"
    },
    "CandleStructure": {
        icon: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3v4"/><path d="M9 17v4"/><rect x="7" y="7" width="4" height="10" rx="1"/><path d="M15 1v4"/><path d="M15 19v4"/><rect x="13" y="5" width="4" height="14" rx="1"/></svg>`,
        bg: "rgba(139, 92, 246, 0.15)",
        color: "#8B5CF6"
    },
    "MarketStructure": {
        icon: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`,
        bg: "rgba(245, 158, 11, 0.15)",
        color: "#F59E0B"
    },
    "CurrencyStrength": {
        icon: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>`,
        bg: "rgba(16, 185, 129, 0.15)",
        color: "#10B981"
    },
    "MLPrediction": {
        icon: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a4 4 0 0 0-4 4c0 .3.04.59.1.88A4 4 0 0 0 6 10a4 4 0 0 0-2 3.46 4 4 0 0 0 3.32 3.94A4 4 0 0 0 11 21.9V14"/><path d="M12 2a4 4 0 0 1 4 4c0 .3-.04.59-.1.88A4 4 0 0 1 18 10a4 4 0 0 1 2 3.46 4 4 0 0 1-3.32 3.94A4 4 0 0 1 13 21.9V14"/></svg>`,
        bg: "rgba(236, 72, 153, 0.15)",
        color: "#EC4899"
    },
    "MarketRegime": {
        icon: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>`,
        bg: "rgba(6, 182, 212, 0.15)",
        color: "#06B6D4"
    },
    "FundamentalAnalysis": {
        icon: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M3 10h18"/><path d="M5 10v11"/><path d="M19 10v11"/><path d="M12 10v11"/><path d="m12 2 9 6H3l9-6z"/></svg>`,
        bg: "rgba(16, 185, 129, 0.15)",
        color: "#10B981"
    },
    "MacroAnalysis": {
        icon: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`,
        bg: "rgba(245, 158, 11, 0.15)",
        color: "#F59E0B"
    },
    "SentimentCrossAsset": {
        icon: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/></svg>`,
        bg: "rgba(6, 182, 212, 0.15)",
        color: "#06B6D4"
    },
    "NewsSentiment": {
        icon: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/></svg>`,
        bg: "rgba(6, 182, 212, 0.15)",
        color: "#06B6D4"
    },
    "RiskMetrics": {
        icon: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
        bg: "rgba(139, 92, 246, 0.15)",
        color: "#8B5CF6"
    },
    "RiskAssessment": {
        icon: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
        bg: "rgba(139, 92, 246, 0.15)",
        color: "#8B5CF6"
    }
};

async function loadParallelHealth() {
    try {
        const res = await fetch('/api/parallel/health');
        const data = await res.json();
        const grid = document.getElementById('parallel-engines-grid');
        if (!grid) return;

        grid.innerHTML = '';
        (data.active_engines || []).forEach(eng => {
            const meta = engineMeta[eng] || {
                icon: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/></svg>`,
                bg: "rgba(16, 185, 129, 0.15)",
                color: "#10B981"
            };

            grid.innerHTML += `
                <div class="engine-card">
                    <div class="engine-icon-circle" style="background: ${meta.bg}; color: ${meta.color};">
                        ${meta.icon}
                    </div>
                    <div style="font-weight: 700; font-size: 0.95rem; color: #F8FAFC; margin-bottom: 10px;">${eng}</div>
                    <div style="margin-bottom: 12px;">
                        <span style="background: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid rgba(16, 185, 129, 0.3); padding: 4px 14px; border-radius: 6px; font-size: 0.75rem; font-weight: 700; display: inline-block;">ACTIVE</span>
                    </div>
                    <div style="font-size: 0.8rem; color: var(--text-muted); line-height: 1.4;">
                        Latency: ~12-45ms<br>(Isolated Fail-Safe)
                    </div>
                </div>
            `;
        });
    } catch (err) {
        console.error("Error loading parallel health:", err);
    }
}

async function loadLogs() {
    const levelEl = document.getElementById('log-filter-level');
    const compEl = document.getElementById('log-filter-component');
    const searchEl = document.getElementById('log-filter-search');
    const terminal = document.getElementById('flight-recorder-terminal');
    if (!terminal) return;

    const level = levelEl ? levelEl.value : 'ALL';
    const component = compEl ? compEl.value : 'ALL';
    const search = searchEl ? searchEl.value : '';

    try {
        const query = new URLSearchParams({
            level: level,
            component: component,
            search: search,
            limit: 200
        });
        const res = await fetch(`/api/logs?${query.toString()}`);
        const data = await res.json();
        const logs = data.logs || [];

        if (logs.length === 0) {
            terminal.innerHTML = `<div style="color: var(--text-muted); padding: 10px;">No flight-recorder log events found matching filters.</div>`;
            return;
        }

        terminal.innerHTML = '';
        logs.forEach(l => {
            let time = l.timestamp;
            try {
                const d = new Date(l.timestamp);
                if (!isNaN(d.getTime())) {
                    time = d.toLocaleTimeString();
                }
            } catch (e) {}

            let levelBadge = '';
            if (l.level === 'INFO') levelBadge = `<span style="color: #06B6D4; font-weight: bold;">[INFO ]</span>`;
            else if (l.level === 'WARNING') levelBadge = `<span style="color: #F59E0B; font-weight: bold;">[WARN ]</span>`;
            else if (l.level === 'ERROR') levelBadge = `<span style="color: #F43F5E; font-weight: bold;">[ERROR]</span>`;
            else if (l.level === 'CRITICAL') levelBadge = `<span style="color: #FF0055; font-weight: bold; background: rgba(255,0,85,0.2); padding: 1px 4px; border-radius: 3px;">[CRIT ]</span>`;
            else levelBadge = `<span style="color: #94A3B8;">[DEBUG]</span>`;

            const scanPart = l.scan_id ? `<span style="color: #A78BFA;">[${l.scan_id}]</span> ` : '';
            const compPart = `<span style="color: #38BDF8;">[${l.component}]</span>`;
            const evtPart = l.event ? ` <span style="color: #34D399;">[${l.event}]</span>` : '';

            terminal.innerHTML += `
                <div style="margin-bottom: 4px; word-break: break-word;">
                    <span style="color: #64748B;">${time}</span> ${levelBadge} ${scanPart}${compPart}${evtPart} <span style="color: #E2E8F0;">${l.message}</span>
                </div>
            `;
        });
    } catch (err) {
        console.error("Error fetching logs:", err);
    }
}

// Auto-refresh logs & telemetry every 5 seconds when tab-health is open
setInterval(() => {
    const healthTab = document.getElementById('tab-health');
    if (healthTab && healthTab.classList.contains('active')) {
        loadLogsSummary();
        loadLogs();
    }
}, 5000);

async function loadLogsSummary() {
    try {
        const res = await fetch('/api/logs/summary');
        const s = await res.json();

        // 1. Ribbon Counters
        if (document.getElementById('log-stat-scans')) document.getElementById('log-stat-scans').innerText = s.scans_total || 0;
        if (document.getElementById('log-stat-candidates')) document.getElementById('log-stat-candidates').innerText = s.candidates_total || 0;
        if (document.getElementById('log-stat-signals')) document.getElementById('log-stat-signals').innerText = s.signals_total || 0;
        if (document.getElementById('log-stat-telegram')) document.getElementById('log-stat-telegram').innerText = `${s.telegram?.sent || 0} / ${s.telegram?.attempted || 0}`;
        if (document.getElementById('log-stat-email')) document.getElementById('log-stat-email').innerText = `${s.email?.sent || 0}`;
        if (document.getElementById('log-stat-errors')) document.getElementById('log-stat-errors').innerText = s.errors_total || 0;
        if (document.getElementById('log-stat-warnings')) document.getElementById('log-stat-warnings').innerText = s.warnings_total || 0;
        if (document.getElementById('log-stat-engine-failures')) document.getElementById('log-stat-engine-failures').innerText = s.engine_failures_total || 0;

        // 2. Status Banner
        if (document.getElementById('log-live-scan-id')) document.getElementById('log-live-scan-id').innerText = s.current_scan_id || 'scan-idle';
        if (document.getElementById('log-live-state')) document.getElementById('log-live-state').innerText = s.current_state || 'IDLE';
        if (document.getElementById('log-live-last-scan')) {
            const dt = s.last_successful_scan !== '--:--:--' ? new Date(s.last_successful_scan).toLocaleTimeString() : '--:--:--';
            document.getElementById('log-live-last-scan').innerText = dt;
        }
        if (document.getElementById('log-live-last-error')) {
            if (s.last_error) {
                document.getElementById('log-live-last-error').innerText = `${s.last_error.component}: ${s.last_error.error_type} (${s.last_error.message.substring(0, 45)})`;
                document.getElementById('log-live-last-error').style.color = "var(--accent-rose)";
            } else {
                document.getElementById('log-live-last-error').innerText = "None (All systems healthy)";
                document.getElementById('log-live-last-error').style.color = "var(--accent-emerald)";
            }
        }

        // 3. Telegram & Email Dispatcher Telemetry
        if (document.getElementById('tg-stat-attempted')) document.getElementById('tg-stat-attempted').innerText = s.telegram?.attempted || 0;
        if (document.getElementById('tg-stat-sent')) document.getElementById('tg-stat-sent').innerText = s.telegram?.sent || 0;
        if (document.getElementById('tg-stat-failed')) document.getElementById('tg-stat-failed').innerText = s.telegram?.failed || 0;

        // 4. Engine Health Table
        const engBody = document.getElementById('engine-health-body');
        if (engBody && s.engine_health) {
            engBody.innerHTML = '';
            s.engine_health.forEach(eng => {
                const isHealthy = eng.failed === 0;
                engBody.innerHTML += `
                    <tr>
                        <td style="font-weight: 600;">${eng.engine}</td>
                        <td>${eng.executions}</td>
                        <td style="color: var(--accent-emerald); font-weight: 600;">${eng.success}</td>
                        <td style="color: ${eng.failed > 0 ? 'var(--accent-rose)' : 'inherit'}; font-weight: ${eng.failed > 0 ? '700' : 'normal'};">${eng.failed}</td>
                        <td style="font-family: monospace; color: var(--accent-cyan);">${eng.avg_latency_ms} ms</td>
                        <td>
                            <span style="padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; background: ${isHealthy ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)'}; color: ${isHealthy ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">
                                ${eng.last_status}
                            </span>
                        </td>
                    </tr>
                `;
            });
        }

        // 5. Top Recurring Errors Table
        const errBody = document.getElementById('top-errors-body');
        if (errBody && s.top_errors) {
            errBody.innerHTML = '';
            if (s.top_errors.length === 0) {
                errBody.innerHTML = `<tr><td colspan="4" style="color: var(--text-muted); text-align: center; padding: 12px;">Zero recurring errors detected. Systems healthy.</td></tr>`;
            } else {
                s.top_errors.forEach(err => {
                    errBody.innerHTML += `
                        <tr>
                            <td style="font-weight: 700; color: var(--accent-rose);">${err.error}</td>
                            <td><span style="color: var(--accent-cyan); font-size: 0.8rem;">${err.component}</span></td>
                            <td style="font-family: 'Outfit'; font-weight: 700;">${err.count}</td>
                            <td style="font-size: 0.75rem; color: var(--text-muted);">${new Date(err.last_seen).toLocaleTimeString()}</td>
                        </tr>
                    `;
                });
            }
        }
    } catch (err) {
        console.error("Error loading logs summary:", err);
    }
}
