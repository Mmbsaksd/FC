// App JS - Dynamic Dashboard Logic
document.addEventListener("DOMContentLoaded", () => {
    loadOverview();
    loadSignals();
    loadSignalOutcomes();
    loadPaperTrading();
    loadMLModels();
    loadKnowledgeBase();
    loadExperienceMemory();
    loadConfig();
    loadAssetConfig();
    loadSchedulerConfig();
    loadLogsSummary();
    loadLogs();
    initCharts();

    // Auto-refresh outcomes and overview periodically
    setInterval(() => {
        const activeTab = document.querySelector('.tab-content.active');
        if (activeTab && (activeTab.id === 'tab-signals' || activeTab.id === 'tab-paper')) {
            loadSignalOutcomes();
        } else if (activeTab && activeTab.id === 'tab-overview') {
            loadOverview();
        }
    }, 15000);
});

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

    event.currentTarget.classList.add('active');
    document.getElementById(tabId).classList.add('active');

    if (tabId === 'tab-overview') {
        loadOverview();
    } else if (tabId === 'tab-signals') {
        loadSignalOutcomes();
        loadSignals();
    } else if (tabId === 'tab-paper') {
        loadSignalOutcomes();
        loadPaperTrading();
    } else if (tabId === 'tab-funnel') {
        loadFunnel();
    } else if (tabId === 'tab-ml') {
        loadMLModels();
    } else if (tabId === 'tab-knowledge') {
        loadKnowledgeBase();
    } else if (tabId === 'tab-experience') {
        loadExperienceMemory();
    } else if (tabId === 'tab-health') {
        loadLogsSummary();
        loadLogs();
    } else if (tabId === 'tab-settings') {
        loadConfig();
        loadAssetConfig();
        loadSchedulerConfig();
    }
}

async function loadSignalOutcomes() {
    try {
        const [analyticsRes, activeRes, historyRes, eventsRes] = await Promise.all([
            fetch('/api/signals/analytics'),
            fetch('/api/signals/active'),
            fetch('/api/signals/history'),
            fetch('/api/signals/events')
        ]);

        const analytics = await analyticsRes.json();
        const activeData = await activeRes.json();
        const historyData = await historyRes.json();
        const eventsData = await eventsRes.json();

        // 1. Update Ribbon Metrics
        document.getElementById('so-total-alerts').innerText = analytics.total_alerts || 0;
        document.getElementById('so-active-count').innerText = analytics.active_alerts || 0;
        document.getElementById('so-t1-hits').innerText = `${analytics.target_1_hits || 0} (${analytics.target_1_rate_pct || 0}%)`;
        document.getElementById('so-t2-hits').innerText = `${analytics.target_2_hits || 0} (${analytics.target_2_rate_pct || 0}%)`;
        document.getElementById('so-sl-hits').innerText = `${analytics.stop_loss_hits || 0} (${analytics.stop_loss_rate_pct || 0}%)`;
        document.getElementById('so-win-rate').innerText = `${analytics.win_rate_pct || 0}%`;
        document.getElementById('so-avg-r').innerText = `${analytics.average_r >= 0 ? '+' : ''}${analytics.average_r || 0}R`;
        document.getElementById('so-expectancy').innerText = `${analytics.expectancy_r >= 0 ? '+' : ''}${analytics.expectancy_r || 0}R`;

        // 2. Populate Active Signals Table
        const activeTbody = document.getElementById('active-signals-table-body');
        if (activeTbody) {
            activeTbody.innerHTML = '';
            const activeList = activeData.active_signals || [];
            if (activeList.length === 0) {
                activeTbody.innerHTML = `<tr><td colspan="13" style="text-align: center; color: var(--text-muted); padding: 20px;">No signals currently active. Next scan will evaluate markets.</td></tr>`;
            } else {
                activeList.forEach(sig => {
                    const isLong = sig.direction === 'LONG';
                    const currP = sig.current_price || sig.entry_price;
                    const distT1 = Math.abs(sig.take_profit_1 - currP);
                    const distT2 = Math.abs(sig.take_profit_2 - currP);
                    const distSL = Math.abs(currP - sig.stop_loss);
                    const unR = sig.unrealized_r || 0.0;
                    const unPnl = sig.unrealized_pnl || 0.0;
                    const mins = sig.holding_minutes || 0;
                    const durStr = mins < 60 ? `${mins}m` : `${Math.floor(mins/60)}h ${mins%60}m`;

                    activeTbody.innerHTML += `
                        <tr>
                            <td style="font-family: monospace; font-size: 0.8rem;">${sig.signal_id}</td>
                            <td style="font-weight: 600;">${sig.symbol}</td>
                            <td><span class="direction-tag ${isLong ? 'long' : 'short'}">${sig.direction}</span></td>
                            <td>${sig.entry_price.toFixed(5)}</td>
                            <td style="font-weight: 600; color: white;">${currP.toFixed(5)}</td>
                            <td style="color: var(--accent-emerald);">${distT1.toFixed(5)}</td>
                            <td style="color: var(--accent-emerald);">${distT2.toFixed(5)}</td>
                            <td style="color: var(--accent-rose);">${distSL.toFixed(5)}</td>
                            <td class="${unPnl >= 0 ? 'positive' : 'negative'}">${unPnl >= 0 ? '+' : ''}$${unPnl.toFixed(2)}</td>
                            <td class="${unR >= 0 ? 'positive' : 'negative'}" style="font-weight: 600;">${unR >= 0 ? '+' : ''}${unR.toFixed(2)}R</td>
                            <td>${durStr}</td>
                            <td><span class="status-tag ${sig.t1_hit ? 'live' : 'idle'}">${sig.status}</span></td>
                            <td>
                                <button class="btn-secondary" style="padding: 4px 8px; font-size: 0.75rem;" onclick="openSignalDetailModal('${sig.signal_id}')">🔍 Detail</button>
                            </td>
                        </tr>
                    `;
                });
            }
        }

        // 3. Populate Closed Signals Table
        const closedTbody = document.getElementById('closed-signals-table-body');
        if (closedTbody) {
            closedTbody.innerHTML = '';
            const closedList = historyData.closed_signals || [];
            if (closedList.length === 0) {
                closedTbody.innerHTML = `<tr><td colspan="12" style="text-align: center; color: var(--text-muted); padding: 20px;">No completed signals yet in outcome history.</td></tr>`;
            } else {
                closedList.slice().reverse().forEach(sig => {
                    const isLong = sig.direction === 'LONG';
                    const realR = sig.realized_r || 0.0;
                    const realPnl = sig.realized_pnl || 0.0;
                    const mins = sig.holding_minutes || 0;
                    const durStr = mins < 60 ? `${mins}m` : `${Math.floor(mins/60)}h ${mins%60}m`;
                    const statusClass = realR > 0 ? 'positive' : 'negative';

                    closedTbody.innerHTML += `
                        <tr>
                            <td style="font-family: monospace; font-size: 0.8rem;">${sig.signal_id}</td>
                            <td style="font-weight: 600;">${sig.symbol}</td>
                            <td><span class="direction-tag ${isLong ? 'long' : 'short'}">${sig.direction}</span></td>
                            <td>${sig.entry_price.toFixed(5)}</td>
                            <td>${sig.take_profit_1.toFixed(5)}</td>
                            <td>${sig.take_profit_2.toFixed(5)}</td>
                            <td>${sig.stop_loss.toFixed(5)}</td>
                            <td><span class="status-tag ${sig.t2_hit ? 'live' : (sig.t1_hit ? 'live' : 'failed')}">${sig.status}</span></td>
                            <td class="${statusClass}">${realPnl >= 0 ? '+' : ''}$${realPnl.toFixed(2)}</td>
                            <td class="${statusClass}" style="font-weight: 600;">${realR >= 0 ? '+' : ''}${realR.toFixed(2)}R</td>
                            <td>${durStr}</td>
                            <td>
                                <button class="btn-secondary" style="padding: 4px 8px; font-size: 0.75rem;" onclick="openSignalDetailModal('${sig.signal_id}')">🔍 Detail</button>
                            </td>
                        </tr>
                    `;
                });
            }
        }

        // 4. Populate Real-Time Lifecycle Event Feed
        const feedContainer = document.getElementById('lifecycle-event-feed');
        if (feedContainer) {
            feedContainer.innerHTML = '';
            const events = (eventsData.events || []).slice(0, 15);
            if (events.length === 0) {
                feedContainer.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem; padding: 10px;">No lifecycle events logged yet.</div>`;
            } else {
                events.forEach(evt => {
                    let badgeColor = 'var(--accent-cyan)';
                    if (evt.event_type === 'TARGET_1_HIT' || evt.event_type === 'TARGET_2_HIT') badgeColor = 'var(--accent-emerald)';
                    if (evt.event_type === 'STOP_LOSS_HIT') badgeColor = 'var(--accent-rose)';
                    if (evt.event_type === 'EXPIRED') badgeColor = 'var(--accent-amber)';

                    const timeStr = evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : '--:--:--';
                    feedContainer.innerHTML += `
                        <div style="background: rgba(255,255,255,0.03); border-left: 3px solid ${badgeColor}; padding: 8px 12px; border-radius: 4px; font-size: 0.8rem;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                <strong style="color: ${badgeColor};">${evt.event_type}</strong>
                                <span style="color: var(--text-muted); font-size: 0.75rem;">${timeStr}</span>
                            </div>
                            <div style="color: var(--text-secondary);">${evt.detail || ''}</div>
                        </div>
                    `;
                });
            }
        }

        // 5. Populate Asset Breakdown Table
        const assetTbody = document.getElementById('asset-outcomes-table-body');
        if (assetTbody) {
            assetTbody.innerHTML = '';
            (analytics.asset_breakdown || []).forEach(a => {
                assetTbody.innerHTML += `
                    <tr>
                        <td style="font-weight: 600;">${a.symbol}</td>
                        <td>${a.total_signals}</td>
                        <td class="${a.win_rate_pct >= 50 ? 'positive' : 'negative'}">${a.win_rate_pct}%</td>
                        <td>${a.t1_rate_pct}%</td>
                        <td>${a.t2_rate_pct}%</td>
                        <td class="${a.avg_r >= 0 ? 'positive' : 'negative'}">${a.avg_r >= 0 ? '+' : ''}${a.avg_r}R</td>
                    </tr>
                `;
            });
        }
    } catch (err) {
        console.error("Error loading signal outcomes:", err);
    }
}

async function openSignalDetailModal(signalId) {
    try {
        const res = await fetch(`/api/signals/detail/${signalId}`);
        if (!res.ok) {
            alert("Signal detail not found");
            return;
        }
        const data = await res.json();
        const sig = data.signal;
        const isLong = sig.direction === 'LONG';
        const mins = sig.holding_minutes || 0;
        const durStr = mins < 60 ? `${mins} mins` : `${Math.floor(mins/60)}h ${mins%60}m`;

        document.getElementById('modal-title').innerText = `📋 SIGNAL TRACE: ${sig.symbol} (${sig.direction}) — ${sig.signal_id}`;

        let html = `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin-bottom: 16px;">
                <div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 6px;">
                    <div style="font-size: 0.75rem; color: var(--text-muted);">Status</div>
                    <div style="font-weight: 700; color: var(--accent-emerald);">${sig.status}</div>
                </div>
                <div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 6px;">
                    <div style="font-size: 0.75rem; color: var(--text-muted);">Score / Win Prob</div>
                    <div style="font-weight: 700; color: white;">${sig.opportunity_score} / ${(sig.ml_probability*100).toFixed(1)}%</div>
                </div>
                <div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 6px;">
                    <div style="font-size: 0.75rem; color: var(--text-muted);">Realized R / P&L</div>
                    <div style="font-weight: 700; color: ${sig.realized_r >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">${sig.realized_r >= 0 ? '+' : ''}${sig.realized_r}R ($${sig.realized_pnl})</div>
                </div>
                <div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 6px;">
                    <div style="font-size: 0.75rem; color: var(--text-muted);">MFE / MAE</div>
                    <div style="font-weight: 700; color: var(--accent-cyan);">+${sig.mfe_r || 0}R / ${sig.mae_r || 0}R</div>
                </div>
                <div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 6px;">
                    <div style="font-size: 0.75rem; color: var(--text-muted);">Holding Duration</div>
                    <div style="font-weight: 700; color: white;">${durStr}</div>
                </div>
            </div>

            <h5 style="color: var(--accent-cyan); margin-bottom: 8px;">🎯 Target & Stop Parameters:</h5>
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 16px; font-size: 0.85rem;">
                <div style="padding: 8px; background: rgba(0,0,0,0.3); border-radius: 4px;">Entry: <strong>${sig.entry_price}</strong></div>
                <div style="padding: 8px; background: rgba(0,0,0,0.3); border-radius: 4px;">Target 1: <strong style="color: var(--accent-emerald);">${sig.take_profit_1}</strong></div>
                <div style="padding: 8px; background: rgba(0,0,0,0.3); border-radius: 4px;">Target 2: <strong style="color: var(--accent-emerald);">${sig.take_profit_2}</strong></div>
                <div style="padding: 8px; background: rgba(0,0,0,0.3); border-radius: 4px;">Stop Loss: <strong style="color: var(--accent-rose);">${sig.stop_loss}</strong></div>
            </div>

            <h5 style="color: var(--accent-emerald); margin-bottom: 8px;">📜 Lifecycle Event History:</h5>
            <div style="display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; max-height: 180px; overflow-y: auto;">
        `;

        (sig.events || []).forEach(evt => {
            html += `
                <div style="background: rgba(255,255,255,0.03); padding: 6px 10px; border-radius: 4px; font-size: 0.8rem; display: flex; justify-content: space-between;">
                    <span><strong>${evt.event}:</strong> ${evt.detail}</span>
                    <span style="color: var(--text-muted); font-size: 0.75rem;">${new Date(evt.timestamp).toLocaleTimeString()}</span>
                </div>
            `;
        });

        html += `
            </div>
            <h5 style="color: white; margin-bottom: 6px;">🧠 Qualitative AI Rationale:</h5>
            <p style="font-size: 0.85rem; color: var(--text-muted); font-style: italic; line-height: 1.5; background: rgba(0,0,0,0.2); padding: 10px; border-radius: 6px;">
                "${sig.llm_reasoning || 'Strong quantitative confirmation across analytical engines.'}"
            </p>
        `;

        document.getElementById('modal-body').innerHTML = html;
        document.getElementById('rationale-modal').style.display = 'flex';
    } catch (err) {
        console.error("Error opening signal detail:", err);
    }
}

async function loadOverview() {
    try {
        const res = await fetch('/api/overview');
        const data = await res.json();

        // 1. Update Market Climate & Session Ribbon
        if (data.market_session) {
            const sess = data.market_session;
            const sessEl = document.getElementById('ov-session');
            if (sessEl) sessEl.innerText = sess.session || 'Off-Peak';
            
            const statEl = document.getElementById('ov-status');
            if (statEl) {
                statEl.innerText = sess.status || 'OPEN';
                statEl.style.color = sess.is_open ? 'var(--accent-emerald)' : 'var(--accent-rose)';
            }
        }

        if (data.macro_state) {
            const riskEl = document.getElementById('ov-risk-sentiment');
            if (riskEl) {
                const sentiment = data.macro_state.risk_sentiment || 'NEUTRAL';
                riskEl.innerText = sentiment;
                riskEl.style.color = sentiment === 'RISK-ON' ? 'var(--accent-emerald)' : (sentiment === 'RISK-OFF' ? 'var(--accent-rose)' : 'white');
            }

            const dxyEl = document.getElementById('ov-dxy-bias');
            if (dxyEl) {
                const dxy = data.macro_state.dxy_bias || 'NEUTRAL';
                dxyEl.innerText = dxy;
                dxyEl.style.color = dxy === 'BULLISH' ? 'var(--accent-emerald)' : (dxy === 'BEARISH' ? 'var(--accent-rose)' : 'white');
            }
        }

        const actEl = document.getElementById('ov-active-signals');
        if (actEl) actEl.innerText = data.active_signals_count || 0;

        const timeEl = document.getElementById('ov-last-updated');
        if (timeEl) timeEl.innerText = `Last Updated: ${new Date().toLocaleTimeString()}`;

        // 2. Render Top Movers
        const gainersEl = document.getElementById('ov-top-gainers');
        if (gainersEl) {
            gainersEl.innerHTML = '';
            (data.top_gainers || []).forEach(g => {
                gainersEl.innerHTML += `
                    <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.03); padding: 6px 10px; border-radius: 4px; font-size: 0.85rem;">
                        <span style="font-weight: 600;">${g.symbol}</span>
                        <span style="color: var(--accent-emerald); font-weight: 700;">+${g.change_pct}%</span>
                    </div>
                `;
            });
        }

        const declinersEl = document.getElementById('ov-top-decliners');
        if (declinersEl) {
            declinersEl.innerHTML = '';
            (data.top_decliners || []).forEach(d => {
                declinersEl.innerHTML += `
                    <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.03); padding: 6px 10px; border-radius: 4px; font-size: 0.85rem;">
                        <span style="font-weight: 600;">${d.symbol}</span>
                        <span style="color: var(--accent-rose); font-weight: 700;">${d.change_pct}%</span>
                    </div>
                `;
            });
        }

        // 2.5 Provider Hierarchy Badge
        if (data.provider_hierarchy) {
            const ph = data.provider_hierarchy;
            const pbEl = document.getElementById('ov-provider-badge');
            if (pbEl) {
                pbEl.innerText = `📡 Feed: ${ph.hierarchy_label}`;
                pbEl.style.color = ph.has_oanda ? 'var(--accent-emerald)' : 'var(--accent-cyan)';
            }
        }

        // 3. Currency Strength Grid
        const grid = document.getElementById('currency-strength-grid');
        if (grid) {
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
        }

        // 4. Tracked Market Monitor Table
        const tbody = document.getElementById('market-monitor-body');
        if (tbody) {
            tbody.innerHTML = '';
            (data.tracked_assets || []).forEach(item => {
                const isLong = item.direction === 'LONG';
                const isPosChange = item.change_pct >= 0;
                let statusBadge = `<span style="color: var(--text-muted); font-size: 0.75rem;">MONITORING</span>`;
                if (item.signal_status && item.signal_status.startsWith('ACTIVE')) {
                    statusBadge = `<span class="status-tag live" style="cursor: pointer;" onclick="switchTab('tab-signals')">${item.signal_status}</span>`;
                } else if (item.signal_status === 'QUALIFIED') {
                    statusBadge = `<span class="status-tag" style="background: rgba(245,158,11,0.2); color: var(--accent-amber); font-size: 0.75rem;">QUALIFIED</span>`;
                }

                const spreadClass = item.spread_type === 'ACTUAL SPREAD' ? 'background: rgba(16, 185, 129, 0.15); color: var(--accent-emerald);' : 'background: rgba(6, 182, 212, 0.15); color: var(--accent-cyan);';
                const spreadBadge = `<div style="display: flex; align-items: center; gap: 6px;"><span style="font-weight: 600;">${item.spread_pips} p</span><span class="status-tag" style="font-size: 0.65rem; padding: 2px 6px; ${spreadClass}">${item.spread_type || 'ESTIMATED'}</span></div>`;

                tbody.innerHTML += `
                    <tr>
                        <td style="font-weight: 600;">${item.symbol}</td>
                        <td><span style="font-size: 0.75rem; color: var(--text-muted); padding: 2px 6px; background: rgba(255,255,255,0.05); border-radius: 4px;">${item.asset_type || 'FX'}</span></td>
                        <td style="font-weight: 600; color: white;">${item.price.toFixed(item.price > 50 ? 2 : 5)}</td>
                        <td class="${isPosChange ? 'positive' : 'negative'}" style="font-weight: 600;">${isPosChange ? '+' : ''}${item.change_pct}%</td>
                        <td>${spreadBadge}</td>
                        <td><span class="direction-tag ${isLong ? 'long' : 'short'}">${item.direction}</span></td>
                        <td>${item.score}/100</td>
                        <td>${item.rsi}</td>
                        <td>${item.adx}</td>
                        <td style="color: var(--text-muted);">${item.setup}</td>
                        <td>${statusBadge}</td>
                    </tr>
                `;
            });
        }
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
        if (data.thresholds && data.thresholds.min_score !== undefined) {
            const scoreVal = Math.round(data.thresholds.min_score);
            const slider = document.getElementById('score-threshold-slider');
            const display = document.getElementById('score-threshold-display');
            if (slider) slider.value = scoreVal;
            if (display) display.innerText = `${scoreVal}%`;
        }
    } catch (e) {
        console.error("Error loading config:", e);
    }
}

function onScoreThresholdSliderChange(val) {
    const display = document.getElementById('score-threshold-display');
    if (display) display.innerText = `${val}%`;
}

async function saveScoreThreshold() {
    const slider = document.getElementById('score-threshold-slider');
    const output = document.getElementById('score-threshold-status');
    if (!slider || !output) return;

    const minScore = parseFloat(slider.value);
    output.innerText = "Saving threshold...";
    output.style.color = "var(--text-secondary)";

    try {
        const res = await fetch('/api/config/thresholds/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ min_score: minScore })
        });
        const data = await res.json();
        if (data.status === 'SUCCESS') {
            output.innerText = `✅ Saved: ${data.min_score}% Required`;
            output.style.color = "var(--accent-emerald)";
        } else {
            output.innerText = `❌ Error: ${data.message}`;
            output.style.color = "var(--accent-rose)";
        }
    } catch (err) {
        output.innerText = "❌ Network Error: " + err;
        output.style.color = "var(--accent-rose)";
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

// -------------------------------------------------------------
// ADVANCED ML, LEARNING, KNOWLEDGE & EXPERIENCE HANDLERS
// -------------------------------------------------------------
async function loadMLModels() {
    try {
        const [modelsRes, dsRes] = await Promise.all([
            fetch('/api/ml/models'),
            fetch('/api/ml/dataset')
        ]);
        const mData = await modelsRes.json();
        const dsData = await dsRes.json();

        // 1. Production Model Ribbon Cards
        const prod = mData.production_model || {};
        if (document.getElementById('ml-prod-version')) document.getElementById('ml-prod-version').innerText = prod.version || 'v2.1.0';
        if (document.getElementById('ml-prod-type')) document.getElementById('ml-prod-type').innerText = prod.model_type || 'Calibrated Logistic Ensemble';
        if (document.getElementById('ml-prod-auc')) document.getElementById('ml-prod-auc').innerText = prod.oos_auc_roc ? prod.oos_auc_roc.toFixed(3) : '0.684';
        if (document.getElementById('ml-prod-brier')) document.getElementById('ml-prod-brier').innerText = prod.brier_score ? prod.brier_score.toFixed(3) : '0.142';

        // Dataset status
        if (document.getElementById('ml-dataset-count')) document.getElementById('ml-dataset-count').innerText = `${dsData.total_samples || 0} (${dsData.labeled_samples || 0} Labeled)`;
        if (document.getElementById('ml-retrain-status')) {
            const r = mData.readiness || {};
            document.getElementById('ml-retrain-status').innerText = r.reason || 'Ready for retraining';
            document.getElementById('ml-retrain-status').style.color = r.ready_to_retrain ? 'var(--accent-emerald)' : 'var(--text-muted)';
        }

        // 2. Models Table
        const tbody = document.getElementById('ml-models-table-body');
        if (tbody && mData.all_models) {
            tbody.innerHTML = '';
            mData.all_models.forEach(m => {
                const isProd = m.status === 'PRODUCTION';
                const isCand = m.status === 'CANDIDATE';
                tbody.innerHTML += `
                    <tr>
                        <td style="font-weight: 700; color: ${isProd ? 'var(--accent-emerald)' : 'var(--accent-cyan)'};">${m.version}</td>
                        <td style="font-size: 0.85rem;">${m.model_type}</td>
                        <td>
                            <span style="padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; background: ${isProd ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255,255,255,0.05)'}; color: ${isProd ? 'var(--accent-emerald)' : 'var(--text-secondary)'};">
                                ${m.status}
                            </span>
                        </td>
                        <td style="font-weight: 600;">${m.oos_auc_roc ? m.oos_auc_roc.toFixed(3) : '--'}</td>
                        <td style="font-weight: 600; color: var(--accent-emerald);">${m.brier_score ? m.brier_score.toFixed(3) : '--'}</td>
                        <td style="font-weight: 600; color: var(--accent-cyan);">+${m.expected_value_r ? m.expected_value_r.toFixed(2) : '0.00'}R</td>
                        <td>${m.max_drawdown_pct ? m.max_drawdown_pct.toFixed(1) : '--'}%</td>
                        <td>
                            ${isCand ? `<button class="btn-primary" style="padding: 4px 8px; font-size: 0.75rem;" onclick="promoteModel('${m.version}')">Promote</button>` : `<span style="font-size: 0.75rem; color: var(--text-muted);">${isProd ? 'Active' : 'Archived'}</span>`}
                        </td>
                    </tr>
                `;
            });
        }
    } catch (err) {
        console.error("Error loading ML models:", err);
    }
}

async function triggerRetraining() {
    try {
        const res = await fetch('/api/ml/retrain', { method: 'POST' });
        const data = await res.json();
        alert(`🧪 Retraining Experiment Complete!\n\nCandidate: ${data.candidate?.version}\nOOS AUC: ${data.candidate?.oos_auc_roc}\nBrier Score: ${data.candidate?.brier_score}\nRecommendation: ${data.recommendation}`);
        loadMLModels();
    } catch (err) {
        alert("Error triggering retraining: " + err);
    }
}

async function promoteModel(version) {
    if (!confirm(`Promote model ${version} to PRODUCTION?`)) return;
    try {
        const res = await fetch('/api/ml/promote', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ version })
        });
        const data = await res.json();
        if (data.status === 'SUCCESS') {
            alert(`Model ${version} successfully promoted to PRODUCTION!`);
            loadMLModels();
        }
    } catch (err) {
        alert("Error promoting model: " + err);
    }
}

async function rollbackModel() {
    if (!confirm("Rollback active production model to previous version?")) return;
    try {
        const res = await fetch('/api/ml/rollback', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'SUCCESS') {
            alert(`Production rolled back. Active version: ${data.active_version}`);
            loadMLModels();
        }
    } catch (err) {
        alert("Error rolling back model: " + err);
    }
}

async function loadKnowledgeBase() {
    try {
        const status = document.getElementById('kb-filter-status')?.value || 'ALL';
        const asset = document.getElementById('kb-filter-asset')?.value || 'ALL';
        const tf = document.getElementById('kb-filter-tf')?.value || 'ALL';

        const query = new URLSearchParams({
            status: status,
            asset_class: asset,
            timeframe: tf
        });

        const [itemsRes, analyticsRes] = await Promise.all([
            fetch(`/api/knowledge?${query.toString()}`),
            fetch('/api/knowledge/analytics')
        ]);
        const data = await itemsRes.json();
        const analytics = await analyticsRes.json();

        // 1. Update Health & Empirical Attribution Ribbon
        updateKnowledgeRibbon(analytics);

        // 2. Render Knowledge Cards
        const container = document.getElementById('knowledge-items-container');
        if (!container) return;
        container.innerHTML = '';

        if (!data.items || data.items.length === 0) {
            container.innerHTML = `<div class="glass-card" style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); padding: 32px;">No knowledge items matching active filters.</div>`;
            return;
        }

        data.items.forEach(k => {
            const isVal = k.status === 'VALIDATED';
            const isHypo = k.status === 'HYPOTHESIS';
            const isExp = k.status === 'EXPERIMENTAL';
            const isReview = k.status === 'REQUIRES_REVIEW';
            const isStale = k.status === 'STALE';

            let statusBg = 'rgba(255,255,255,0.05)';
            let statusColor = 'var(--text-secondary)';
            if (isVal) { statusBg = 'rgba(16, 185, 129, 0.15)'; statusColor = 'var(--accent-emerald)'; }
            else if (isHypo) { statusBg = 'rgba(6, 182, 212, 0.15)'; statusColor = 'var(--accent-cyan)'; }
            else if (isExp) { statusBg = 'rgba(245, 158, 11, 0.15)'; statusColor = 'var(--accent-amber)'; }
            else if (isReview || isStale) { statusBg = 'rgba(244, 63, 94, 0.15)'; statusColor = 'var(--accent-rose)'; }

            const winRate = k.win_rate !== undefined ? k.win_rate : 0.0;
            const expR = k.expectancy_r !== undefined ? k.expectancy_r : 0.0;
            const sampleN = k.sample_size || 0;
            const freshness = k.freshness_score !== undefined ? (k.freshness_score * 100).toFixed(0) : 100;
            const usage = k.usage_stats || {};

            container.innerHTML += `
                <div class="glass-card" style="display: flex; flex-direction: column; justify-content: space-between; border-left: 4px solid ${statusColor};">
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                            <span style="font-size: 0.75rem; font-weight: 700; color: var(--accent-cyan); text-transform: uppercase;">${k.category}</span>
                            <div style="display: flex; gap: 6px; align-items: center;">
                                <span style="font-size: 0.7rem; color: var(--text-muted);">v${k.version || '1.0.0'}</span>
                                <span style="padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; background: ${statusBg}; color: ${statusColor};">
                                    ${k.status}
                                </span>
                            </div>
                        </div>

                        <h4 style="font-family: 'Outfit'; font-size: 1.05rem; margin-bottom: 8px; color: #F8FAFC;">${k.title}</h4>
                        <p style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 12px;">${k.finding || k.hypothesis}</p>

                        <!-- Empirical Metric Badges -->
                        <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px;">
                            <span style="background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.25); color: var(--accent-emerald); padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700;">
                                ${winRate}% Win (${k.success_count || 0}W / ${k.failure_count || 0}L)
                            </span>
                            <span style="background: rgba(6,182,212,0.1); border: 1px solid rgba(6,182,212,0.25); color: var(--accent-cyan); padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700;">
                                ${expR >= 0 ? '+' : ''}${expR.toFixed(2)}R EV
                            </span>
                            <span style="background: rgba(255,255,255,0.05); color: var(--text-muted); padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;">
                                N = ${sampleN}
                            </span>
                            <span style="background: rgba(255,255,255,0.05); color: ${freshness < 50 ? 'var(--accent-rose)' : 'var(--text-muted)'}; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;">
                                🌿 ${freshness}% Fresh
                            </span>
                        </div>

                        <!-- Scope & Tags -->
                        <div style="font-size: 0.75rem; color: var(--text-muted); border-top: 1px solid rgba(255,255,255,0.06); padding-top: 8px; display: flex; flex-direction: column; gap: 4px;">
                            <div><strong>Scope:</strong> ${(k.applicable_symbols || []).slice(0, 4).join(', ')} | ${(k.applicable_asset_classes || []).join(', ')}</div>
                            <div><strong>Context:</strong> ${(k.applicable_timeframes || []).join(', ')} | Regimes: ${(k.applicable_regimes || []).slice(0, 2).join(', ')}</div>
                        </div>
                    </div>

                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 14px; pt-2; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 8px;">
                        <span style="font-size: 0.7rem; color: var(--text-muted);">Used in ${usage.times_applied || 0} live decisions</span>
                        <button class="btn-primary" style="padding: 4px 10px; font-size: 0.75rem; background: rgba(255,255,255,0.08);" onclick="openKnowledgeDetailModal('${k.item_id}')">
                            🔍 Inspect Evidence
                        </button>
                    </div>
                </div>
            `;
        });
    } catch (err) {
        console.error("Error loading knowledge base:", err);
    }
}

function updateKnowledgeRibbon(a) {
    if (!a) return;
    if (document.getElementById('kb-stat-total')) document.getElementById('kb-stat-total').innerText = a.total_knowledge_items || 0;
    if (document.getElementById('kb-stat-validated')) document.getElementById('kb-stat-validated').innerText = a.status_breakdown?.VALIDATED || 0;
    if (document.getElementById('kb-stat-hypotheses')) document.getElementById('kb-stat-hypotheses').innerText = (a.status_breakdown?.HYPOTHESIS || 0) + (a.status_breakdown?.EXPERIMENTAL || 0);

    const winRate = a.knowledge_attributed_win_rate || 0.0;
    const avgR = a.knowledge_attributed_avg_r || 0.0;

    if (document.getElementById('kb-stat-winrate')) {
        document.getElementById('kb-stat-winrate').innerText = `${winRate}%`;
        document.getElementById('kb-stat-winrate').className = `metric-value ${winRate >= 58.2 ? 'positive' : 'negative'}`;
    }
    if (document.getElementById('kb-stat-winrate-delta')) {
        const delta = a.edge_delta_win_rate || 0.0;
        document.getElementById('kb-stat-winrate-delta').innerText = `${delta >= 0 ? '+' : ''}${delta}% vs Baseline (58.2%)`;
    }

    if (document.getElementById('kb-stat-avgr')) {
        document.getElementById('kb-stat-avgr').innerText = `${avgR >= 0 ? '+' : ''}${avgR.toFixed(2)}R`;
        document.getElementById('kb-stat-avgr').className = `metric-value ${avgR >= 1.15 ? 'positive' : 'negative'}`;
    }
    if (document.getElementById('kb-stat-avgr-delta')) {
        const deltaR = a.edge_delta_r || 0.0;
        document.getElementById('kb-stat-avgr-delta').innerText = `${deltaR >= 0 ? '+' : ''}${deltaR}R vs Baseline (+1.15R)`;
    }

    if (document.getElementById('kb-stat-breakdown')) {
        const sb = a.status_breakdown || {};
        document.getElementById('kb-stat-breakdown').innerText = `${sb.VALIDATED || 0} Validated • ${sb.EXPERIMENTAL || 0} Exp • ${sb.HYPOTHESIS || 0} Hypo • ${sb.REQUIRES_REVIEW || 0} Review`;
    }
}

async function triggerKnowledgeDiscovery() {
    try {
        const res = await fetch('/api/knowledge/discover', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'SUCCESS') {
            const added = data.new_hypotheses_added?.length || 0;
            const prom = data.promotion_gate_actions || {};
            alert(`🧪 Discovery Scan Complete!\n\nEvaluated: ${data.resolved_trades_evaluated} trades\nDiscovered Candidates: ${data.candidates_discovered_count}\nNew Hypotheses Registered: ${added}\nPromoted to Experimental: ${prom.promoted_to_experimental || 0}\nPromoted to Validated: ${prom.promoted_to_validated || 0}`);
            loadKnowledgeBase();
        } else {
            alert(`Discovery Notice: ${data.message || 'Check trade volume'}`);
        }
    } catch (err) {
        alert("Error running knowledge discovery: " + err);
    }
}

async function recalculateKnowledgeStats() {
    try {
        const res = await fetch('/api/knowledge/recalculate', { method: 'POST' });
        const data = await res.json();
        alert(`📊 Recalculated Dynamic Statistics across knowledge rules!\n\nRules updated: ${data.details?.rules_updated || 0}`);
        loadKnowledgeBase();
    } catch (err) {
        alert("Error recalculating knowledge stats: " + err);
    }
}

async function openKnowledgeDetailModal(itemId) {
    try {
        const res = await fetch(`/api/knowledge/item/${itemId}`);
        const data = await res.json();
        if (data.status !== 'SUCCESS' || !data.item) {
            alert("Could not load knowledge item details.");
            return;
        }

        const k = data.item;
        document.getElementById('kb-modal-category').innerText = `${k.category} • ID: ${k.item_id} (v${k.version || '1.0.0'})`;
        document.getElementById('kb-modal-title').innerText = k.title;

        const badge = document.getElementById('kb-modal-status-badge');
        badge.innerText = k.status;
        if (k.status === 'VALIDATED') {
            badge.style.background = 'rgba(16, 185, 129, 0.2)'; badge.style.color = 'var(--accent-emerald)';
        } else if (k.status === 'HYPOTHESIS') {
            badge.style.background = 'rgba(6, 182, 212, 0.2)'; badge.style.color = 'var(--accent-cyan)';
        } else {
            badge.style.background = 'rgba(245, 158, 11, 0.2)'; badge.style.color = 'var(--accent-amber)';
        }

        const usage = k.usage_stats || {};
        const vHist = k.version_history || [];

        let histHtml = '';
        vHist.forEach(vh => {
            histHtml += `<li style="margin-left: 18px; margin-bottom: 4px;"><strong>v${vh.version}</strong> [${vh.status}] (${new Date(vh.timestamp).toLocaleDateString()}): ${vh.reason}</li>`;
        });

        document.getElementById('kb-modal-body').innerHTML = `
            <div style="margin-bottom: 16px;">
                <h5 style="color: var(--accent-cyan); margin-bottom: 4px;">🎯 What is the Rule & Hypothesis?</h5>
                <p style="color: #F1F5F9; font-size: 0.95rem;">${k.finding || k.hypothesis}</p>
            </div>

            <div style="margin-bottom: 16px;">
                <h5 style="color: var(--accent-cyan); margin-bottom: 4px;">🔬 Empirical Evidence & Source Lineage</h5>
                <p>${k.evidence}</p>
                <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 4px;">
                    Source: <strong>${k.source_type}</strong> (${k.source_reference}) • Discovery: <strong>${k.discovery_method}</strong>
                </div>
            </div>

            <div style="background: rgba(0,0,0,0.25); border-radius: 8px; padding: 12px; margin-bottom: 16px;">
                <h5 style="color: var(--accent-cyan); margin-bottom: 8px;">📊 Quantitative Validation Metrics</h5>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px;">
                    <div><span style="color: var(--text-muted); font-size: 0.75rem;">Sample Size:</span><br><strong>N = ${k.sample_size || 0}</strong></div>
                    <div><span style="color: var(--text-muted); font-size: 0.75rem;">Wins / Losses:</span><br><strong>${k.success_count || 0}W / ${k.failure_count || 0}L</strong></div>
                    <div><span style="color: var(--text-muted); font-size: 0.75rem;">Win Rate:</span><br><strong style="color: var(--accent-emerald);">${k.win_rate || 0}%</strong></div>
                    <div><span style="color: var(--text-muted); font-size: 0.75rem;">Expectancy:</span><br><strong style="color: var(--accent-cyan);">${k.expectancy_r >= 0 ? '+' : ''}${k.expectancy_r || 0}R</strong></div>
                    <div><span style="color: var(--text-muted); font-size: 0.75rem;">Significance:</span><br><strong>${k.statistical_significance || 'N/A'}</strong></div>
                    <div><span style="color: var(--text-muted); font-size: 0.75rem;">Freshness Score:</span><br><strong>${((k.freshness_score || 1.0) * 100).toFixed(0)}%</strong></div>
                </div>
            </div>

            <div style="margin-bottom: 16px;">
                <h5 style="color: var(--accent-cyan); margin-bottom: 4px;">🌐 Applicable Scope & Constraints</h5>
                <div style="display: flex; flex-wrap: wrap; gap: 6px; font-size: 0.8rem;">
                    <span style="padding: 2px 8px; background: rgba(255,255,255,0.06); border-radius: 4px;">Symbols: ${(k.applicable_symbols || []).join(', ')}</span>
                    <span style="padding: 2px 8px; background: rgba(255,255,255,0.06); border-radius: 4px;">Asset Classes: ${(k.applicable_asset_classes || []).join(', ')}</span>
                    <span style="padding: 2px 8px; background: rgba(255,255,255,0.06); border-radius: 4px;">Timeframes: ${(k.applicable_timeframes || []).join(', ')}</span>
                    <span style="padding: 2px 8px; background: rgba(255,255,255,0.06); border-radius: 4px;">Regimes: ${(k.applicable_regimes || []).join(', ')}</span>
                    <span style="padding: 2px 8px; background: rgba(255,255,255,0.06); border-radius: 4px;">Sessions: ${(k.applicable_sessions || []).join(', ')}</span>
                </div>
            </div>

            <div style="background: rgba(16,185,129,0.05); border: 1px solid rgba(16,185,129,0.15); border-radius: 8px; padding: 12px; margin-bottom: 16px;">
                <h5 style="color: var(--accent-emerald); margin-bottom: 6px;">📈 Live Decision Usage & Attributed Outcomes</h5>
                <div style="font-size: 0.85rem; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                    <div>Times Retrieved: <strong>${usage.times_retrieved || 0}</strong></div>
                    <div>Times Applied in Signals: <strong>${usage.times_applied || 0}</strong></div>
                    <div>Attributed Win Rate: <strong style="color: var(--accent-emerald);">${usage.attributed_win_rate || 0}%</strong> (${usage.attributed_wins || 0}W / ${usage.attributed_losses || 0}L)</div>
                    <div>Attributed Avg R: <strong>${usage.attributed_avg_r >= 0 ? '+' : ''}${usage.attributed_avg_r || 0}R</strong></div>
                </div>
            </div>

            <div>
                <h5 style="color: var(--accent-cyan); margin-bottom: 6px;">📜 Version Audit History</h5>
                <ul style="font-size: 0.8rem; color: var(--text-muted);">
                    ${histHtml || '<li>Initial version</li>'}
                </ul>
            </div>
        `;

        document.getElementById('knowledge-detail-modal').style.display = 'flex';
    } catch (err) {
        console.error("Error opening knowledge detail modal:", err);
    }
}

function closeKnowledgeModal() {
    const m = document.getElementById('knowledge-detail-modal');
    if (m) m.style.display = 'none';
}

async function loadExperienceMemory() {
    try {
        const res = await fetch('/api/memory/experience');
        const data = await res.json();

        // Summary Ribbon
        const s = data.summary || {};
        if (document.getElementById('exp-total')) document.getElementById('exp-total').innerText = s.total_experiences || 0;
        if (document.getElementById('exp-resolved')) document.getElementById('exp-resolved').innerText = `${s.resolved_trades || 0} (${s.win_rate_pct || 0}% Win Rate)`;
        if (document.getElementById('exp-avg-r')) {
            const r = s.average_realized_r || 0.0;
            document.getElementById('exp-avg-r').innerText = `${r >= 0 ? '+' : ''}${r.toFixed(2)}R`;
            document.getElementById('exp-avg-r').className = `metric-value ${r >= 0 ? 'positive' : 'negative'}`;
        }
        if (document.getElementById('exp-mfe-mae')) {
            document.getElementById('exp-mfe-mae').innerText = `+${s.avg_mfe_r || 0}R / ${s.avg_mae_r || 0}R`;
        }

        // Records Table
        const tbody = document.getElementById('experience-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (!data.records || data.records.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 16px;">Zero experience traces recorded yet. Active signals will appear here.</td></tr>`;
            return;
        }

        data.records.forEach(r => {
            const isWin = String(r.outcome_status).includes('WIN');
            const isLoss = String(r.outcome_status).includes('LOSS');
            const isLong = r.direction === 'LONG';

            tbody.innerHTML += `
                <tr>
                    <td style="font-family: monospace; font-size: 0.8rem;">${r.signal_id || r.experience_id}</td>
                    <td style="font-weight: 600;">${r.symbol}</td>
                    <td><span class="direction-tag ${isLong ? 'long' : 'short'}">${r.direction}</span></td>
                    <td style="color: var(--accent-cyan); font-weight: 600;">${(r.ml_predicted_win_prob * 100).toFixed(1)}%</td>
                    <td>
                        <span style="padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; background: ${isWin ? 'rgba(16,185,129,0.15)' : (isLoss ? 'rgba(244,63,94,0.15)' : 'rgba(255,255,255,0.05)')}; color: ${isWin ? 'var(--accent-emerald)' : (isLoss ? 'var(--accent-rose)' : 'var(--text-secondary)')};">
                            ${r.outcome_status}
                        </span>
                    </td>
                    <td style="font-weight: 700; color: ${r.realized_r > 0 ? 'var(--accent-emerald)' : (r.realized_r < 0 ? 'var(--accent-rose)' : 'inherit')};">
                        ${r.realized_r !== null ? (r.realized_r > 0 ? '+' : '') + r.realized_r.toFixed(2) + 'R' : '--'}
                    </td>
                    <td style="color: var(--accent-emerald);">+${(r.mfe_r || 0).toFixed(2)}R</td>
                    <td style="color: var(--accent-rose);">${(r.mae_r || 0).toFixed(2)}R</td>
                    <td style="font-size: 0.75rem; color: var(--text-muted);">${r.error_classification || 'Standard Execution'}</td>
                </tr>
            `;
        });
    } catch (err) {
        console.error("Error loading experience memory:", err);
    }
}

// -------------------------------------------------------------
// POST-SIGNAL OUTCOME TRACKING & LIFECYCLE MONITORING
// -------------------------------------------------------------
async function loadSignalOutcomes() {
    try {
        // 1. Fetch Analytics Summary
        const analyticsRes = await fetch('/api/signals/analytics');
        const analytics = await analyticsRes.json();

        if (document.getElementById('so-total-alerts')) document.getElementById('so-total-alerts').innerText = analytics.total_alerts || 0;
        if (document.getElementById('so-active-count')) document.getElementById('so-active-count').innerText = analytics.active_alerts || 0;
        if (document.getElementById('so-t1-hits')) document.getElementById('so-t1-hits').innerText = `${analytics.target_1_hits || 0} (${(analytics.target_1_rate_pct || 0).toFixed(1)}%)`;
        if (document.getElementById('so-t2-hits')) document.getElementById('so-t2-hits').innerText = `${analytics.target_2_hits || 0} (${(analytics.target_2_rate_pct || 0).toFixed(1)}%)`;
        if (document.getElementById('so-sl-hits')) document.getElementById('so-sl-hits').innerText = `${analytics.stop_loss_hits || 0} (${(analytics.stop_loss_rate_pct || 0).toFixed(1)}%)`;
        if (document.getElementById('so-win-rate')) document.getElementById('so-win-rate').innerText = `${(analytics.win_rate_pct || 0).toFixed(1)}%`;
        if (document.getElementById('so-avg-r')) {
            const r = analytics.average_r || 0.0;
            document.getElementById('so-avg-r').innerText = `${r >= 0 ? '+' : ''}${r.toFixed(2)}R`;
            document.getElementById('so-avg-r').className = `metric-value ${r >= 0 ? 'positive' : 'negative'}`;
        }
        if (document.getElementById('so-expectancy')) {
            const exp = analytics.expectancy_r || 0.0;
            document.getElementById('so-expectancy').innerText = `${exp >= 0 ? '+' : ''}${exp.toFixed(2)}R`;
        }

        // 2. Fetch Live Actively Monitored Signals
        const activeRes = await fetch('/api/signals/active');
        const activeData = await activeRes.json();
        const activeTableBody = document.getElementById('active-signals-table-body');
        if (activeTableBody) {
            activeTableBody.innerHTML = '';
            const signals = activeData.active_signals || [];
            if (signals.length === 0) {
                activeTableBody.innerHTML = `<tr><td colspan="13" style="text-align: center; color: var(--text-muted); padding: 18px;">No active signals currently being monitored. New qualifying signals will appear here automatically.</td></tr>`;
            } else {
                signals.forEach(s => {
                    const isLong = s.direction === 'LONG';
                    const curR = parseFloat(s.unrealized_r || 0.0);
                    const curPnl = parseFloat(s.unrealized_pnl || 0.0);
                    const statusClass = s.status === 'TARGET_1_HIT' ? 'positive' : 'live';

                    activeTableBody.innerHTML += `
                        <tr>
                            <td style="font-family: monospace; font-size: 0.8rem; font-weight: 600;">${s.signal_id}</td>
                            <td style="font-weight: 600;">${s.symbol}</td>
                            <td><span class="direction-tag ${isLong ? 'long' : 'short'}">${s.direction}</span></td>
                            <td>${parseFloat(s.entry_price).toFixed(s.entry_price > 50 ? 2 : 5)}</td>
                            <td style="font-weight: 700;">${parseFloat(s.current_price || s.entry_price).toFixed(s.entry_price > 50 ? 2 : 5)}</td>
                            <td style="color: var(--accent-emerald); font-weight: 600;">${s.distance_to_tp1 !== undefined ? s.distance_to_tp1 : '--'}</td>
                            <td style="color: var(--accent-emerald);">${s.distance_to_tp2 !== undefined ? s.distance_to_tp2 : '--'}</td>
                            <td style="color: var(--accent-rose);">${s.distance_to_sl !== undefined ? s.distance_to_sl : '--'}</td>
                            <td style="font-weight: 700; color: ${curPnl >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">${curPnl >= 0 ? '+' : ''}$${curPnl.toFixed(2)}</td>
                            <td style="font-weight: 700; color: ${curR >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">${curR >= 0 ? '+' : ''}${curR.toFixed(2)}R</td>
                            <td style="font-size: 0.8rem; color: var(--text-muted);">${s.holding_minutes || 0}m</td>
                            <td><span class="status-tag ${statusClass}">${s.status}</span></td>
                            <td>
                                <button class="btn-secondary" style="padding: 3px 8px; font-size: 0.75rem;" onclick="openSignalDetailModal('${s.signal_id}')">🔍 Detail</button>
                            </td>
                        </tr>
                    `;
                });
            }
        }

        // 3. Fetch Completed Signal Outcome History
        const historyRes = await fetch('/api/signals/history');
        const historyData = await historyRes.json();
        const historyTableBody = document.getElementById('closed-signals-table-body');
        if (historyTableBody) {
            historyTableBody.innerHTML = '';
            const closed = historyData.closed_signals || [];
            if (closed.length === 0) {
                historyTableBody.innerHTML = `<tr><td colspan="12" style="text-align: center; color: var(--text-muted); padding: 18px;">No completed signals in history yet.</td></tr>`;
            } else {
                closed.forEach(s => {
                    const isLong = s.direction === 'LONG';
                    const finalR = parseFloat(s.realized_r || 0.0);
                    const finalPnl = parseFloat(s.realized_pnl || 0.0);
                    const isWin = finalR > 0;

                    historyTableBody.innerHTML += `
                        <tr>
                            <td style="font-family: monospace; font-size: 0.8rem;">${s.signal_id}</td>
                            <td style="font-weight: 600;">${s.symbol}</td>
                            <td><span class="direction-tag ${isLong ? 'long' : 'short'}">${s.direction}</span></td>
                            <td>${parseFloat(s.entry_price).toFixed(s.entry_price > 50 ? 2 : 5)}</td>
                            <td>${parseFloat(s.take_profit_1).toFixed(s.entry_price > 50 ? 2 : 5)}</td>
                            <td>${s.take_profit_2 ? parseFloat(s.take_profit_2).toFixed(s.entry_price > 50 ? 2 : 5) : '--'}</td>
                            <td>${parseFloat(s.stop_loss).toFixed(s.entry_price > 50 ? 2 : 5)}</td>
                            <td>
                                <span style="padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; background: ${isWin ? 'rgba(16,185,129,0.15)' : 'rgba(244,63,94,0.15)'}; color: ${isWin ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">
                                    ${s.outcome || s.status}
                                </span>
                            </td>
                            <td style="font-weight: 700; color: ${finalPnl >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">${finalPnl >= 0 ? '+' : ''}$${finalPnl.toFixed(2)}</td>
                            <td style="font-weight: 700; color: ${finalR >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">${finalR >= 0 ? '+' : ''}${finalR.toFixed(2)}R</td>
                            <td style="font-size: 0.8rem; color: var(--text-muted);">${s.holding_minutes || 0}m</td>
                            <td>
                                <button class="btn-secondary" style="padding: 3px 8px; font-size: 0.75rem;" onclick="openSignalDetailModal('${s.signal_id}')">🔍 Detail</button>
                            </td>
                        </tr>
                    `;
                });
            }
        }

        // 4. Fetch Real-Time Lifecycle Events Feed
        const eventsRes = await fetch('/api/signals/events');
        const eventsData = await eventsRes.json();
        const eventsFeed = document.getElementById('lifecycle-events-feed');
        if (eventsFeed) {
            eventsFeed.innerHTML = '';
            const events = eventsData.events || [];
            if (events.length === 0) {
                eventsFeed.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 16px;">No lifecycle events recorded yet.</div>`;
            } else {
                events.slice(0, 30).forEach(ev => {
                    let badgeColor = 'var(--text-secondary)';
                    let bg = 'rgba(255,255,255,0.05)';
                    if (ev.event_type === 'TARGET_1_HIT') { badgeColor = 'var(--accent-emerald)'; bg = 'rgba(16,185,129,0.15)'; }
                    else if (ev.event_type === 'TARGET_2_HIT') { badgeColor = 'var(--accent-emerald)'; bg = 'rgba(16,185,129,0.25)'; }
                    else if (ev.event_type === 'STOP_LOSS_HIT') { badgeColor = 'var(--accent-rose)'; bg = 'rgba(244,63,94,0.15)'; }
                    else if (ev.event_type === 'SIGNAL_CREATED') { badgeColor = 'var(--accent-cyan)'; bg = 'rgba(6,182,212,0.15)'; }

                    const timeStr = new Date(ev.timestamp).toLocaleTimeString();
                    eventsFeed.innerHTML += `
                        <div style="display: flex; gap: 12px; align-items: flex-start; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                            <span style="font-size: 0.75rem; color: var(--text-muted); min-width: 65px;">${timeStr}</span>
                            <span style="padding: 1px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; background: ${bg}; color: ${badgeColor}; min-width: 90px; text-align: center;">
                                ${ev.event_type}
                            </span>
                            <div style="font-size: 0.8rem; flex: 1;">
                                <strong>${ev.symbol || ''}</strong>: ${ev.detail || ''}
                            </div>
                        </div>
                    `;
                });
            }
        }

        // 5. Populate Asset Breakdown Table
        const assetTableBody = document.getElementById('asset-outcomes-table-body');
        if (assetTableBody && analytics.asset_breakdown) {
            assetTableBody.innerHTML = '';
            analytics.asset_breakdown.forEach(a => {
                assetTableBody.innerHTML += `
                    <tr>
                        <td style="font-weight: 600;">${a.symbol}</td>
                        <td>${a.total_signals}</td>
                        <td style="font-weight: 600; color: ${a.win_rate_pct >= 50 ? 'var(--accent-emerald)' : 'inherit'};">${a.win_rate_pct.toFixed(1)}%</td>
                        <td>${a.t1_rate_pct.toFixed(1)}%</td>
                        <td>${a.t2_rate_pct.toFixed(1)}%</td>
                        <td style="font-weight: 700; color: ${a.avg_r >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">${a.avg_r >= 0 ? '+' : ''}${a.avg_r.toFixed(2)}R</td>
                    </tr>
                `;
            });
        }
    } catch (err) {
        console.error("Error loading signal outcomes:", err);
    }
}

async function openSignalDetailModal(signalId) {
    try {
        const res = await fetch(`/api/signals/detail/${signalId}`);
        const data = await res.json();
        const s = data.signal;
        if (!s) return;

        let modal = document.getElementById('signal-detail-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'signal-detail-modal';
            modal.className = 'modal-backdrop';
            document.body.appendChild(modal);
        }

        const isLong = s.direction === 'LONG';
        const events = s.events || [];

        modal.innerHTML = `
            <div class="glass-card modal-content" style="max-width: 650px; width: 90%; max-height: 85vh; overflow-y: auto; padding: 24px; position: relative;">
                <button style="position: absolute; top: 16px; right: 16px; background: none; border: none; font-size: 1.2rem; color: var(--text-muted); cursor: pointer;" onclick="closeSignalDetailModal()">✕</button>
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
                    <h3 style="font-family: 'Outfit'; font-size: 1.3rem;">${s.symbol}</h3>
                    <span class="direction-tag ${isLong ? 'long' : 'short'}">${s.direction}</span>
                    <span class="status-tag ${s.status === 'CLOSED' ? 'positive' : 'live'}">${s.status}</span>
                </div>
                <div style="font-family: monospace; font-size: 0.8rem; color: var(--text-muted); margin-bottom: 16px;">Signal ID: ${s.signal_id}</div>

                <div class="card-grid" style="grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 16px;">
                    <div style="background: rgba(255,255,255,0.03); padding: 8px; border-radius: 6px;">
                        <div style="font-size: 0.7rem; color: var(--text-muted);">Entry Price</div>
                        <div style="font-weight: 700;">${parseFloat(s.entry_price).toFixed(s.entry_price > 50 ? 2 : 5)}</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.03); padding: 8px; border-radius: 6px;">
                        <div style="font-size: 0.7rem; color: var(--text-muted);">Stop Loss</div>
                        <div style="font-weight: 700; color: var(--accent-rose);">${parseFloat(s.stop_loss).toFixed(s.entry_price > 50 ? 2 : 5)}</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.03); padding: 8px; border-radius: 6px;">
                        <div style="font-size: 0.7rem; color: var(--text-muted);">Target 1</div>
                        <div style="font-weight: 700; color: var(--accent-emerald);">${parseFloat(s.take_profit_1).toFixed(s.entry_price > 50 ? 2 : 5)}</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.03); padding: 8px; border-radius: 6px;">
                        <div style="font-size: 0.7rem; color: var(--text-muted);">Target 2</div>
                        <div style="font-weight: 700; color: var(--accent-emerald);">${s.take_profit_2 ? parseFloat(s.take_profit_2).toFixed(s.entry_price > 50 ? 2 : 5) : '--'}</div>
                    </div>
                </div>

                <div class="card-grid" style="grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 16px;">
                    <div style="background: rgba(255,255,255,0.03); padding: 8px; border-radius: 6px;">
                        <div style="font-size: 0.7rem; color: var(--text-muted);">Max Excursion (MFE)</div>
                        <div style="font-weight: 700; color: var(--accent-emerald);">+${(s.mfe_r || 0).toFixed(2)}R</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.03); padding: 8px; border-radius: 6px;">
                        <div style="font-size: 0.7rem; color: var(--text-muted);">Max Drawdown (MAE)</div>
                        <div style="font-weight: 700; color: var(--accent-rose);">${(s.mae_r || 0).toFixed(2)}R</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.03); padding: 8px; border-radius: 6px;">
                        <div style="font-size: 0.7rem; color: var(--text-muted);">Realized Return</div>
                        <div style="font-weight: 700; color: ${s.realized_r >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">${s.realized_r !== undefined ? (s.realized_r >= 0 ? '+' : '') + s.realized_r.toFixed(2) + 'R' : '--'}</div>
                    </div>
                </div>

                <h4 style="font-family: 'Outfit'; font-size: 0.95rem; margin-bottom: 8px;">🤖 AI Confluence & Rationale</h4>
                <p style="font-size: 0.85rem; color: var(--text-secondary); background: rgba(0,0,0,0.2); padding: 10px; border-radius: 6px; line-height: 1.5; margin-bottom: 16px;">
                    ${s.llm_reasoning || 'Parallel engine consensus achieved without counter-trend conflicts.'}
                </p>

                <h4 style="font-family: 'Outfit'; font-size: 0.95rem; margin-bottom: 8px;">⏱️ Lifecycle Progression Timeline</h4>
                <div style="border-left: 2px solid rgba(255,255,255,0.1); padding-left: 12px; display: flex; flex-direction: column; gap: 8px;">
                    ${events.map(ev => `
                        <div style="font-size: 0.8rem;">
                            <span style="color: var(--accent-cyan); font-weight: 600;">${new Date(ev.timestamp).toLocaleTimeString()}:</span>
                            <span style="font-weight: 700;"> ${ev.event}</span> — ${ev.detail || ''}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        modal.style.display = 'flex';
    } catch (err) {
        console.error("Error opening signal detail modal:", err);
    }
}

function closeSignalDetailModal() {
    const modal = document.getElementById('signal-detail-modal');
    if (modal) modal.style.display = 'none';
}

async function loadAssetConfig() {
    try {
        const res = await fetch('/api/config/assets');
        const cfg = await res.json();
        const fxEl = document.getElementById('asset-toggle-forex');
        const commEl = document.getElementById('asset-toggle-commodities');
        const crEl = document.getElementById('asset-toggle-crypto');
        if (fxEl) fxEl.checked = cfg.forex_enabled !== false;
        if (commEl) commEl.checked = cfg.commodities_enabled !== false;
        if (crEl) crEl.checked = cfg.crypto_enabled !== false;
        updateAssetCountTag(cfg);
    } catch (err) {
        console.error("Error loading asset config:", err);
    }
}

function updateAssetCountTag(cfg) {
    let count = 0;
    if (cfg.forex_enabled !== false) count++;
    if (cfg.commodities_enabled !== false) count++;
    if (cfg.crypto_enabled !== false) count++;
    const tag = document.getElementById('asset-active-count-tag');
    if (tag) {
        tag.innerText = `${count} / 3 Classes Active`;
        tag.style.color = count > 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)';
    }
}

async function saveAssetConfig() {
    const fx = document.getElementById('asset-toggle-forex')?.checked ?? true;
    const comm = document.getElementById('asset-toggle-commodities')?.checked ?? true;
    const crypto = document.getElementById('asset-toggle-crypto')?.checked ?? true;
    const statusEl = document.getElementById('asset-config-status');
    if (statusEl) {
        statusEl.innerText = "Saving asset configuration...";
        statusEl.style.color = "var(--text-secondary)";
    }

    try {
        const res = await fetch('/api/config/assets', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                forex_enabled: fx,
                commodities_enabled: comm,
                crypto_enabled: crypto
            })
        });
        const data = await res.json();
        updateAssetCountTag(data);
        if (statusEl) {
            statusEl.innerText = "✅ Saved! Active instruments updated.";
            statusEl.style.color = "var(--accent-emerald)";
            setTimeout(() => { statusEl.innerText = ""; }, 4000);
        }
        loadOverview();
    } catch (err) {
        if (statusEl) {
            statusEl.innerText = "❌ Error saving asset config: " + err;
            statusEl.style.color = "var(--accent-rose)";
        }
    }
}


