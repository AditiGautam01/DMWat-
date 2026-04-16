// State
let state = {
    tables: [],
    activeTable: null,
    activeMaximo: null, // Track currently selected Maximo entity
    currentView: 'welcome', // welcome, table, sql
    maximoSource: null, // 'synthetic' or 'live'
    activeStream: null, // EventSource instance for active stream
};

const maximoEntities = [
    { id: 'workorders', name: 'Work Orders', icon: 'wrench' },
    { id: 'assets', name: 'Assets', icon: 'cube' },
    { id: 'service_requests', name: 'Service Requests', icon: 'ticket' }
];

// DOM Elements
const el = {
    tableList: document.getElementById('table-list'),
    maximoList: document.getElementById('maximo-list'),
    maximoSourceBadge: document.getElementById('maximo-source-badge'),
    activeEntity: document.getElementById('active-entity'),
    viewWelcome: document.getElementById('view-welcome'),
    viewTable: document.getElementById('view-table'),
    viewSql: document.getElementById('view-sql'),
    btnSqlMode: document.getElementById('btn-sql-mode'),
    inputQuestion: document.getElementById('input-question'),
    resultsArea: document.getElementById('results-area'),
    resultTitle: document.getElementById('result-title'),
    resultContent: document.getElementById('result-content'),
    loadingIndicator: document.getElementById('loading-indicator'),
    dataPreviewContainer: document.getElementById('data-preview-container'),
    dataPreviewTable: document.getElementById('data-preview-table'),
    inputSql: document.getElementById('input-sql'),
    sqlResultsArea: document.getElementById('sql-results-area'),
    loadingIndicatorSql: document.getElementById('loading-indicator-sql'),
    generatedSqlBlock: document.getElementById('generated-sql-block'),
    sqlExecutionResults: document.getElementById('sql-execution-results'),
    streamPanel: document.getElementById('stream-panel'),
    streamFeed: document.getElementById('stream-feed'),
    streamCounter: document.getElementById('stream-counter'),
    streamLive: document.getElementById('stream-live-indicator'),
    // Pipeline elements
    viewPipeline: document.getElementById('view-pipeline'),
    btnPipelineMode: document.getElementById('btn-pipeline-mode'),
    pipelineTable: document.getElementById('pipeline-table'),
    pipelineEntity: document.getElementById('pipeline-entity'),
    pipelineQuestion: document.getElementById('pipeline-question'),
    pipelineLoading: document.getElementById('pipeline-loading'),
    pipelineSteps: document.getElementById('pipeline-steps'),
    pipelineFeeds: document.getElementById('pipeline-feeds'),
    pipelineDb2Feed: document.getElementById('pipeline-db2-feed'),
    pipelineMaximoFeed: document.getElementById('pipeline-maximo-feed'),
    pipelineAnswer: document.getElementById('pipeline-answer'),
    pipelineAnswerContent: document.getElementById('pipeline-answer-content'),
    pipelineData: document.getElementById('pipeline-data'),
    pipelineDb2Table: document.getElementById('pipeline-db2-table'),
    pipelineMaximoTable: document.getElementById('pipeline-maximo-table'),
};

// Initialize
async function init() {
    try {
        const response = await fetch('/api/tables');
        const data = await response.json();
        
        // Filter out empty tables, just show some key ones or all
        state.tables = data.tables;
        
        renderTableList();
        renderMaximoList();
        
        // Check Maximo source status
        checkMaximoStatus();
        
        // Setup listeners
        el.inputQuestion.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') app.askQuestion();
        });
        
        el.btnSqlMode.addEventListener('click', () => app.switchView('sql'));
        if (el.btnPipelineMode) {
            el.btnPipelineMode.addEventListener('click', () => app.switchView('pipeline'));
        }

        // Populate pipeline table dropdown
        if (el.pipelineTable) {
            el.pipelineTable.innerHTML = '';
            state.tables.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.name;
                opt.textContent = t.name;
                el.pipelineTable.appendChild(opt);
            });
        }
        
        // Default to pipeline view instead of welcome screen
        app.switchView('pipeline');
        
    } catch (err) {
        el.tableList.innerHTML = `<div style="color:var(--error); padding: 12px;"><i class="ph ph-warning"></i> Error loading schema. Is Db2 running?</div>`;
        console.error(err);
    }
}

async function checkMaximoStatus() {
    try {
        const res = await fetch('/api/maximo/status');
        const data = await res.json();
        state.maximoSource = data.source;
        
        if (el.maximoSourceBadge) {
            el.maximoSourceBadge.className = `maximo-source-badge ${data.source}`;
            el.maximoSourceBadge.innerHTML = data.source === 'synthetic'
                ? '<i class="ph ph-flask"></i> Synthetic'
                : '<i class="ph ph-broadcast"></i> Live';
            el.maximoSourceBadge.title = data.message;
        }
    } catch (err) {
        console.warn('Could not check Maximo status:', err);
    }
}

function renderTableList() {
    el.tableList.innerHTML = '';
    state.tables.forEach(table => {
        const div = document.createElement('div');
        div.className = `table-item ${state.activeTable === table.name ? 'active' : ''}`;
        div.innerHTML = `<i class="ph ph-table"></i> ${table.name}`;
        div.onclick = () => app.selectTable(table.name);
        el.tableList.appendChild(div);
    });
}

function renderMaximoList() {
    if (!el.maximoList) return;
    el.maximoList.innerHTML = '';
    maximoEntities.forEach(entity => {
        const div = document.createElement('div');
        div.className = `table-item ${state.activeMaximo === entity.id ? 'active' : ''}`;
        div.innerHTML = `<i class="ph ph-${entity.icon}"></i> ${entity.name}`;
        div.onclick = () => app.selectMaximo(entity.id, entity.name);
        el.maximoList.appendChild(div);
    });
}

function renderDataTable(rows, container) {
    if (!rows || rows.length === 0) {
        container.innerHTML = '<div>No data returned.</div>';
        return;
    }
    const cols = Object.keys(rows[0]);
    let html = '<table><thead><tr>';
    cols.forEach(c => html += `<th>${c}</th>`);
    html += '</tr></thead><tbody>';
    
    rows.forEach(r => {
        html += '<tr>';
        cols.forEach(c => html += `<td>${r[c] !== null ? r[c] : '<em>NULL</em>'}</td>`);
        html += '</tr>';
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

// ------------------------------------------------------------------
// Streaming helpers
// ------------------------------------------------------------------
function getRecordId(record) {
    return record.wonum || record.assetnum || record.ticketid || '—';
}

function getRecordDescription(record) {
    return record.description || '—';
}

function getRecordStatus(record) {
    return record.status || '';
}

function renderStreamRecord(record) {
    const id = getRecordId(record);
    const desc = getRecordDescription(record);
    const status = getRecordStatus(record);
    const statusClass = status.toLowerCase().replace(/\s+/g, '');

    const div = document.createElement('div');
    div.className = 'stream-record';
    div.innerHTML = `
        <span class="record-id">${id}</span>
        <span class="record-desc" title="${desc}">${desc}</span>
        <span class="record-status">
            <span class="status-pill ${statusClass}">${status}</span>
        </span>
    `;
    return div;
}

function stopActiveStream() {
    if (state.activeStream) {
        state.activeStream.close();
        state.activeStream = null;
    }
    if (el.streamLive) el.streamLive.classList.add('hidden');
}

// Global App Functions
const app = {
    switchView: (viewName) => {
        state.currentView = viewName;
        document.querySelectorAll('.view-state').forEach(v => v.classList.remove('active'));
        
        if (viewName === 'welcome') el.viewWelcome.classList.add('active');
        if (viewName === 'table') el.viewTable.classList.add('active');
        if (viewName === 'sql') {
            el.viewSql.classList.add('active');
            el.activeEntity.innerHTML = `<i class="ph ph-magic-wand"></i> Natural Language to SQL`;
            state.activeTable = null;
            state.activeMaximo = null;
            renderTableList(); // Remove active state
            renderMaximoList();
        }

        if (viewName === 'pipeline') {
            el.viewPipeline.classList.add('active');
            el.activeEntity.innerHTML = `<i class="ph ph-flow-arrow"></i> Unified Pipeline: Db2 → Maximo → watsonx.ai`;
            state.activeTable = null;
            state.activeMaximo = null;
            renderTableList();
            renderMaximoList();
        }

        // Hide stream panel when leaving maximo context
        if (viewName !== 'table' || !state.activeMaximo) {
            if (el.streamPanel) el.streamPanel.classList.add('hidden');
            stopActiveStream();
        }
    },
    
    selectTable: (tableName) => {
        stopActiveStream();
        state.activeTable = tableName;
        state.activeMaximo = null;
        el.activeEntity.innerHTML = `<i class="ph ph-table"></i> Table: ${tableName}`;
        renderTableList();
        renderMaximoList();
        
        // Reset UI
        el.resultsArea.classList.add('hidden');
        el.inputQuestion.value = '';
        el.inputQuestion.placeholder = "Ask a question about this table (e.g. 'Who is the highest paid?')";
        if (el.streamPanel) el.streamPanel.classList.add('hidden');
        
        app.switchView('table');
    },

    selectMaximo: (entityId, entityName) => {
        stopActiveStream();
        state.activeMaximo = entityId;
        state.activeTable = null;

        const sourceBadge = state.maximoSource === 'synthetic'
            ? '<span class="maximo-source-badge synthetic"><i class="ph ph-flask"></i> Synthetic</span>'
            : '<span class="maximo-source-badge live"><i class="ph ph-broadcast"></i> Live</span>';

        el.activeEntity.innerHTML = `<i class="ph ph-wrench"></i> Maximo: ${entityName} ${sourceBadge}`;
        renderMaximoList();
        renderTableList();
        
        // Reset UI
        el.resultsArea.classList.add('hidden');
        el.inputQuestion.value = '';
        el.inputQuestion.placeholder = `Ask a question about ${entityName}...`;
        
        // Show stream panel
        if (el.streamPanel) {
            el.streamPanel.classList.remove('hidden');
            el.streamFeed.innerHTML = '';
            el.streamCounter.innerHTML = 'Ready to stream';
        }
        
        app.switchView('table');
    },

    // Start streaming Maximo data via SSE
    startStream: () => {
        if (!state.activeMaximo) return;
        stopActiveStream();

        const endpoint = `/api/maximo/stream/${state.activeMaximo}?limit=30`;
        const eventSource = new EventSource(endpoint);
        state.activeStream = eventSource;

        // Clear feed
        el.streamFeed.innerHTML = '';
        el.streamLive.classList.remove('hidden');
        let count = 0;

        eventSource.addEventListener('record', (e) => {
            const record = JSON.parse(e.data);
            count++;
            const card = renderStreamRecord(record);
            el.streamFeed.appendChild(card);
            el.streamCounter.innerHTML = `<span class="count">${count}</span> records received`;
            // Auto-scroll
            el.streamFeed.scrollTop = el.streamFeed.scrollHeight;
        });

        eventSource.addEventListener('done', (e) => {
            const info = JSON.parse(e.data);
            eventSource.close();
            state.activeStream = null;
            el.streamLive.classList.add('hidden');

            const summary = document.createElement('div');
            summary.className = 'stream-summary';
            summary.innerHTML = `<i class="ph ph-check-circle"></i> Stream complete — ${info.total} records received`;
            el.streamFeed.appendChild(summary);
            el.streamCounter.innerHTML = `<span class="count">${info.total}</span> records (done)`;
        });

        eventSource.addEventListener('error', (e) => {
            eventSource.close();
            state.activeStream = null;
            el.streamLive.classList.add('hidden');
            el.streamCounter.innerHTML = '<span style="color:var(--error)">Stream error</span>';
        });
    },

    stopStream: () => {
        stopActiveStream();
        el.streamCounter.innerHTML = 'Stream stopped';
    },

    focusQuestion: () => {
        el.inputQuestion.focus();
    },
    
    summarizeTable: async () => {
        if (!state.activeTable && !state.activeMaximo) return;
        
        if (state.activeMaximo) {
             el.inputQuestion.value = "Provide a general summary of the records.";
             return app.askQuestion();
        }
        
        el.resultsArea.classList.remove('hidden');
        el.resultTitle.innerHTML = `<i class="ph ph-sparkle"></i> AI Summary for ${state.activeTable}`;
        el.loadingIndicator.classList.remove('hidden');
        el.resultContent.innerHTML = '';
        el.dataPreviewTable.innerHTML = '';
        el.dataPreviewContainer.classList.add('hidden');
        
        try {
            const res = await fetch('/api/summarize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ table_name: state.activeTable })
            });
            
            if (!res.ok) {
                const text = await res.text();
                let errDetail = text;
                try { errDetail = JSON.parse(text).detail || text; } catch(e) {}
                throw new Error(errDetail);
            }
            
            const data = await res.json();
            
            el.resultContent.textContent = data.summary;
            el.dataPreviewContainer.classList.remove('hidden');
            renderDataTable(data.rows, el.dataPreviewTable);
            
        } catch(err) {
            el.resultContent.innerHTML = `<span style="color:var(--error)">Error: ${err.message}</span>`;
        } finally {
            el.loadingIndicator.classList.add('hidden');
        }
    },
    
    askQuestion: async () => {
        const q = el.inputQuestion.value.trim();
        if ((!state.activeTable && !state.activeMaximo) || !q) return;
        
        el.resultsArea.classList.remove('hidden');
        el.resultTitle.innerHTML = `<i class="ph ph-robot"></i> Answer to: "${q}"`;
        el.loadingIndicator.classList.remove('hidden');
        el.resultContent.innerHTML = '';
        el.dataPreviewTable.innerHTML = '';
        el.dataPreviewContainer.classList.add('hidden');
        
        try {
            let res;
            if (state.activeTable) {
                res = await fetch('/api/question', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ table_name: state.activeTable, question: q })
                });
            } else if (state.activeMaximo) {
                res = await fetch('/api/maximo/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ data_type: state.activeMaximo, question: q })
                });
            }
            
            if (!res.ok) {
                const text = await res.text();
                let errDetail = text;
                try { errDetail = JSON.parse(text).detail || text; } catch(e) {}
                throw new Error(errDetail);
            }
            
            const data = await res.json();
            
            el.resultContent.textContent = data.answer;
            el.dataPreviewContainer.classList.remove('hidden');
            renderDataTable(data.rows, el.dataPreviewTable);
            
        } catch(err) {
            el.resultContent.innerHTML = `<span style="color:var(--error)">Error: ${err.message}</span>`;
        } finally {
            el.loadingIndicator.classList.add('hidden');
        }
    },
    
    generateSql: async () => {
        const q = el.inputSql.value.trim();
        if (!q) return;
        
        el.sqlResultsArea.classList.remove('hidden');
        el.loadingIndicatorSql.classList.remove('hidden');
        el.generatedSqlBlock.textContent = '';
        el.sqlExecutionResults.innerHTML = '';
        
        try {
            const res = await fetch('/api/sql', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ request: q })
            });
            
            if (!res.ok) {
                const text = await res.text();
                let errDetail = text;
                try { errDetail = JSON.parse(text).detail || text; } catch(e) {}
                throw new Error(errDetail);
            }
            
            const data = await res.json();
            
            if (data.detail) {
                 el.generatedSqlBlock.innerHTML = `<span style="color:var(--error)">Db2 Execution Error: ${data.detail}</span>`;
                 return;
            }
            
            el.generatedSqlBlock.textContent = data.sql;
            if (data.error) {
                el.sqlExecutionResults.innerHTML = `<div style="color:var(--error)">Db2 Execution Error: ${data.error}</div>`;
            } else {
                renderDataTable(data.rows, el.sqlExecutionResults);
            }
            
        } catch(err) {
            el.generatedSqlBlock.innerHTML = `<span style="color:var(--error)">API Error: ${err.message}</span>`;
        } finally {
            el.loadingIndicatorSql.classList.add('hidden');
        }
    },

    // ---------------------------------------------------------------
    // Unified Pipeline: Db2 → Maximo → watsonx.ai (batch)
    // ---------------------------------------------------------------
    runPipeline: async () => {
        const tableName = el.pipelineTable?.value;
        const entity = el.pipelineEntity?.value || 'workorders';
        const question = el.pipelineQuestion?.value?.trim();
        if (!tableName || !question) return;

        // Reset UI
        el.pipelineLoading.classList.remove('hidden');
        el.pipelineSteps.classList.remove('hidden');
        el.pipelineFeeds.classList.add('hidden');
        el.pipelineAnswer.classList.add('hidden');
        el.pipelineData.classList.add('hidden');
        stopActiveStream();

        // Animate steps
        const setStep = (id, status, cls) => {
            const el = document.getElementById(`step-${id}-status`);
            const step = document.getElementById(`step-${id}`);
            if (el) el.textContent = status;
            if (step) {
                step.classList.remove('active', 'done');
                if (cls) step.classList.add(cls);
            }
        };

        setStep('db2', 'querying...', 'active');
        setStep('maximo', 'waiting', '');
        setStep('watsonx', 'waiting', '');

        try {
            const res = await fetch('/api/pipeline/unified', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    table_name: tableName,
                    maximo_entity: entity,
                    question: question,
                    max_rows: 15,
                }),
            });

            if (!res.ok) {
                const text = await res.text();
                let errDetail = text;
                try { errDetail = JSON.parse(text).detail || text; } catch(e) {}
                throw new Error(errDetail);
            }

            const data = await res.json();

            // Update steps
            setStep('db2', `${data.db2_row_count} rows`, 'done');
            setStep('maximo', `${data.maximo_record_count} records`, 'done');
            setStep('watsonx', 'complete', 'done');

            // Show answer
            el.pipelineAnswer.classList.remove('hidden');
            el.pipelineAnswerContent.textContent = data.answer;

            // Show data tables
            el.pipelineData.classList.remove('hidden');
            renderDataTable(data.db2_rows, el.pipelineDb2Table);
            renderDataTable(data.maximo_records, el.pipelineMaximoTable);

        } catch (err) {
            setStep('db2', 'error', '');
            el.pipelineAnswer.classList.remove('hidden');
            el.pipelineAnswerContent.innerHTML = `<span style="color:var(--error)">Pipeline Error: ${err.message}</span>`;
        } finally {
            el.pipelineLoading.classList.add('hidden');
        }
    },

    // ---------------------------------------------------------------
    // Unified Pipeline: Db2 → Maximo → watsonx.ai (streaming)
    // ---------------------------------------------------------------
    streamPipeline: () => {
        const tableName = el.pipelineTable?.value;
        const entity = el.pipelineEntity?.value || 'workorders';
        if (!tableName) return;
        stopActiveStream();

        // Reset UI
        el.pipelineSteps.classList.remove('hidden');
        el.pipelineFeeds.classList.remove('hidden');
        el.pipelineAnswer.classList.add('hidden');
        el.pipelineData.classList.add('hidden');
        el.pipelineDb2Feed.innerHTML = '';
        el.pipelineMaximoFeed.innerHTML = '';

        const setStep = (id, status, cls) => {
            const statusEl = document.getElementById(`step-${id}-status`);
            const stepEl = document.getElementById(`step-${id}`);
            if (statusEl) statusEl.textContent = status;
            if (stepEl) {
                stepEl.classList.remove('active', 'done');
                if (cls) stepEl.classList.add(cls);
            }
        };

        setStep('db2', 'streaming...', 'active');
        setStep('maximo', 'waiting', '');
        setStep('watsonx', 'waiting', '');

        const endpoint = `/api/pipeline/unified/stream?table_name=${encodeURIComponent(tableName)}&maximo_entity=${entity}&max_rows=15`;
        const es = new EventSource(endpoint);
        state.activeStream = es;

        let db2Count = 0;
        let maximoCount = 0;

        es.addEventListener('db2_row', (e) => {
            const row = JSON.parse(e.data);
            db2Count++;
            setStep('db2', `${db2Count} rows`, 'active');

            // Render a compact card for the Db2 row
            const div = document.createElement('div');
            div.className = 'stream-record';
            const id = row.EMPNO || row.DEPTNO || row.PROJNO || Object.values(row)[0] || '';
            const desc = row.FIRSTNME ? `${row.FIRSTNME} ${row.LASTNAME || ''}` : (row.DEPTNAME || row.PROJNAME || JSON.stringify(row).substring(0, 60));
            div.innerHTML = `
                <span class="record-id">${id}</span>
                <span class="record-desc">${desc}</span>
                <span class="record-status"><span class="status-pill operating">DB2</span></span>
            `;
            el.pipelineDb2Feed.appendChild(div);
            el.pipelineDb2Feed.scrollTop = el.pipelineDb2Feed.scrollHeight;
        });

        es.addEventListener('maximo', (e) => {
            const record = JSON.parse(e.data);
            maximoCount++;
            if (maximoCount === 1) {
                setStep('db2', `${db2Count} rows`, 'done');
                setStep('maximo', `streaming...`, 'active');
            } else {
                setStep('maximo', `${maximoCount} records`, 'active');
            }

            const card = renderStreamRecord(record);
            el.pipelineMaximoFeed.appendChild(card);
            el.pipelineMaximoFeed.scrollTop = el.pipelineMaximoFeed.scrollHeight;
        });

        es.addEventListener('done', (e) => {
            const info = JSON.parse(e.data);
            es.close();
            state.activeStream = null;
            setStep('db2', `${info.db2_rows} rows`, 'done');
            setStep('maximo', `${info.maximo_records} records`, 'done');
            setStep('watsonx', 'ready', 'done');

            // Add completion summary to feeds
            const summary = document.createElement('div');
            summary.className = 'stream-summary';
            summary.innerHTML = `<i class="ph ph-check-circle"></i> Pipeline stream complete — ${info.db2_rows} Db2 rows → ${info.maximo_records} Maximo records`;
            el.pipelineMaximoFeed.appendChild(summary);
        });

        es.addEventListener('error', () => {
            es.close();
            state.activeStream = null;
            setStep('db2', 'error', '');
            setStep('maximo', 'error', '');
        });
    },
};

// Start
init();
