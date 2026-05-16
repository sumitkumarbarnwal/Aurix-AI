// ===========================
//  Aurix AI — dashboard.js
//  Connected to Flask API backend
// ===========================

(() => {
  'use strict';

  const API_BASE = window.location.origin;

  // --- Auth check ---
  const currentUser = JSON.parse(localStorage.getItem('aurix-user') || 'null');
  const sessionId = localStorage.getItem('aurix-session') || '';

  if (!currentUser) {
    window.location.href = 'index.html';
    return;
  }

  // Update avatar/user info in the navbar
  const avatarEl = document.getElementById('dash-avatar');
  if (currentUser.picture && avatarEl) {
    avatarEl.innerHTML = `<img src="${currentUser.picture}" alt="${currentUser.name}" style="width:100%;height:100%;border-radius:50%;object-fit:cover;" />`;
  }

  // Sign Out handler
  const signoutBtn = document.getElementById('dash-signout');
  signoutBtn && signoutBtn.addEventListener('click', (e) => {
    e.preventDefault();
    fetch(`${API_BASE}/api/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    }).catch(() => {});
    localStorage.removeItem('aurix-user');
    localStorage.removeItem('aurix-session');
    window.location.href = 'index.html';
  });

  // --- Theme Toggle ---
  const themeToggle = document.getElementById('dash-theme-toggle');
  const htmlEl = document.documentElement;

  const savedTheme = localStorage.getItem('aurix-theme') || 'dark';
  if (savedTheme === 'light') {
    htmlEl.setAttribute('data-theme', 'light');
  }

  themeToggle && themeToggle.addEventListener('click', () => {
    const current = htmlEl.getAttribute('data-theme');
    const next = current === 'light' ? 'dark' : 'light';
    if (next === 'light') {
      htmlEl.setAttribute('data-theme', 'light');
    } else {
      htmlEl.removeAttribute('data-theme');
    }
    localStorage.setItem('aurix-theme', next);
  });

  // --- Nav link active state ---
  const navLinks = document.querySelectorAll('.dash-nav-link');
  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      navLinks.forEach(l => l.classList.remove('active'));
      link.classList.add('active');
    });
  });

  // --- Tab switching ---
  const tabs = document.querySelectorAll('.atab');
  const panes = document.querySelectorAll('.tab-pane');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;
      tabs.forEach(t => t.classList.remove('active'));
      panes.forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      const pane = document.querySelector(`[data-pane="${target}"]`);
      if (pane) pane.classList.add('active');
    });
  });

  // --- URL Input validation ---
  const urlInput = document.getElementById('url-input');
  const urlCheckBtn = document.getElementById('url-check-btn');
  const pipelineProgress = document.getElementById('pipeline-progress');
  const pipDots = document.querySelectorAll('.pip-dot');
  const langSelect = document.getElementById('lang-select');

  function isValidUrl(str) {
    try {
      const url = new URL(str);
      return url.protocol === 'http:' || url.protocol === 'https:';
    } catch {
      return false;
    }
  }

  // --- URL check + submit ---
  urlCheckBtn && urlCheckBtn.addEventListener('click', () => {
    const val = urlInput.value.trim();
    if (!val) return;

    if (isValidUrl(val)) {
      urlCheckBtn.classList.add('valid');
      startRealProcessing(val, null);
    } else {
      urlCheckBtn.classList.remove('valid');
      showNotification('Please enter a valid URL', 'error');
    }
  });

  urlInput && urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      urlCheckBtn.click();
    }
  });

  // --- URL History click to fill ---
  document.querySelectorAll('.url-history-item').forEach(item => {
    item.addEventListener('click', () => {
      const text = item.querySelector('span:last-child').textContent;
      urlInput.value = text;
      urlInput.focus();
    });
  });

  // --- Browse files button ---
  const browseBtn = document.getElementById('browse-btn');
  const fileInput = document.getElementById('file-input');

  browseBtn && browseBtn.addEventListener('click', () => {
    fileInput.click();
  });

  fileInput && fileInput.addEventListener('change', (e) => {
    const files = e.target.files;
    if (files.length > 0) {
      showNotification(`File selected: ${files[0].name}`, 'success');
      startRealProcessing(null, files[0]);
    }
  });

  // --- Drag and drop ---
  const dropZone = document.getElementById('drop-zone');

  if (dropZone) {
    ['dragenter', 'dragover'].forEach(ev => {
      dropZone.addEventListener(ev, (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
      });
    });

    ['dragleave', 'drop'].forEach(ev => {
      dropZone.addEventListener(ev, (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
      });
    });

    dropZone.addEventListener('drop', (e) => {
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        showNotification(`File dropped: ${files[0].name}`, 'success');
        startRealProcessing(null, files[0]);
      }
    });
  }

  // --- File type card click ---
  document.querySelectorAll('.file-type-card').forEach(card => {
    card.addEventListener('click', () => {
      fileInput.accept = card.querySelector('span').textContent;
      fileInput.click();
    });
  });

  // ═══════════════════════════════════════════════════
  //  REAL PROCESSING — Calls Flask API
  // ═══════════════════════════════════════════════════

  let activeSessionId = sessionId;

  async function startRealProcessing(url, file) {
    // Reset pipeline UI
    resetPipeline();
    showNotification('Starting analysis...', 'info');

    try {
      // Build request
      const formData = new FormData();
      formData.append('session_id', activeSessionId);
      formData.append('language', langSelect ? langSelect.value : 'english');

      if (file) {
        formData.append('file', file);
      } else if (url) {
        formData.append('url', url);
      }

      // Start processing
      const res = await fetch(`${API_BASE}/api/process`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });

      const data = await res.json();

      if (!data.success) {
        showNotification(data.error || 'Processing failed', 'error');
        return;
      }

      activeSessionId = data.session_id;

      // Start SSE polling for progress
      pollStatus(activeSessionId);

    } catch (err) {
      console.error('Processing error:', err);
      showNotification('Failed to start processing. Is the server running?', 'error');

      // Fall back to simulation if server is not available
      showNotification('Running in demo mode (simulated)', 'info');
      simulateProcessing(url || file.name);
    }
  }

  function pollStatus(sid) {
    const eventSource = new EventSource(`${API_BASE}/api/status/stream/${sid}`);

    eventSource.onmessage = (event) => {
      const status = JSON.parse(event.data);
      updatePipelineUI(status);

      if (status.step === 'complete') {
        eventSource.close();
        fetchResult(sid);
      }

      if (status.step === 'error') {
        eventSource.close();
        showNotification('Error: ' + status.detail, 'error');
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      // Fallback: poll via GET
      pollStatusFallback(sid);
    };
  }

  async function pollStatusFallback(sid) {
    let running = true;
    let retries = 0;
    const MAX_RETRIES = 5;
    while (running) {
      try {
        const res = await fetch(`${API_BASE}/api/status/${sid}`);
        if (!res.ok) {
          retries++;
          if (retries >= MAX_RETRIES) {
            running = false;
            showNotification('Session not found. Please resubmit.', 'error');
            break;
          }
          await new Promise(r => setTimeout(r, 2000));
          continue;
        }
        retries = 0;
        const status = await res.json();
        updatePipelineUI(status);

        if (status.step === 'complete') {
          running = false;
          fetchResult(sid);
        } else if (status.step === 'error' || status.step === 'unknown') {
          running = false;
          showNotification('Error: ' + (status.detail || 'Processing failed'), 'error');
        } else {
          await new Promise(r => setTimeout(r, 1000));
        }
      } catch {
        running = false;
      }
    }
  }

  function updatePipelineUI(status) {
    const progress = status.progress || 0;
    pipelineProgress.style.width = `${progress}%`;

    // Map steps to pipeline dots
    const step = status.step || '';

    // Reset all dots
    pipDots.forEach(d => d.classList.remove('active', 'processing'));

    // Step 1: Audio
    if (['audio', 'audio_done', 'transcription', 'transcription_done', 'title', 'title_done', 'summary', 'summary_done', 'extraction', 'extraction_done', 'rag', 'rag_done', 'complete'].includes(step)) {
      pipDots[0].classList.add(step === 'audio' ? 'processing' : 'active');
    }

    // Step 2: Text Processing
    if (['transcription', 'transcription_done', 'title', 'title_done', 'summary', 'summary_done', 'extraction', 'extraction_done', 'rag', 'rag_done', 'complete'].includes(step)) {
      pipDots[1].classList.add(step === 'transcription' ? 'processing' : 'active');
    }

    // Step 3: Semantic Analysis
    if (['summary', 'summary_done', 'extraction', 'extraction_done', 'rag', 'rag_done', 'complete'].includes(step)) {
      pipDots[2].classList.add(['summary', 'extraction'].includes(step) ? 'processing' : 'active');
    }

    // Step 4: Report
    if (['rag', 'rag_done', 'complete'].includes(step)) {
      pipDots[3].classList.add(step === 'rag' ? 'processing' : 'active');
    }

    // Show detail
    if (status.detail) {
      showNotification(status.detail, 'info');
    }
  }

  async function fetchResult(sid) {
    try {
      const res = await fetch(`${API_BASE}/api/result/${sid}`);
      const data = await res.json();

      if (data.success && data.result) {
        displayResults(data.result);
        showNotification('Analysis complete!', 'success');
      }
    } catch (err) {
      console.error('Fetch result error:', err);
    }
  }

  // ═══════════════════════════════════════════════════
  //  DISPLAY RESULTS
  // ═══════════════════════════════════════════════════

  function displayResults(result) {
    // Update title
    const titleEl = document.getElementById('dash-title');
    if (result.title && titleEl) {
      titleEl.textContent = result.title;
    }

    // Smart Summary tab
    const summaryPane = document.getElementById('pane-smart-summary');
    if (summaryPane && result.summary) {
      summaryPane.innerHTML = `
        <div class="result-section" style="animation: fadeIn 0.5s ease;">
          <h3 class="result-title">Smart Summary</h3>
          <div class="result-content" style="line-height: 1.8;">
            ${parseMarkdown(result.summary)}
          </div>
        </div>
      `;
    }

    // Fact Check tab → Action Items
    const factPane = document.getElementById('pane-fact-check');
    if (factPane && result.action_items) {
      factPane.innerHTML = `
        <div class="result-section">
          <h3 class="result-title">✅ Action Items</h3>
          <div class="result-content">${formatResultText(result.action_items)}</div>
        </div>`;
    }

    // Synthesis tab → Key Decisions
    const synthPane = document.getElementById('pane-synthesis');
    if (synthPane && result.key_decisions) {
      synthPane.innerHTML = `
        <div class="result-section">
          <h3 class="result-title">🔑 Key Decisions</h3>
          <div class="result-content">${formatResultText(result.key_decisions)}</div>
        </div>`;
    }

    // Verification tab → Open Questions
    const verifyPane = document.getElementById('pane-verification');
    if (verifyPane && result.open_questions) {
      verifyPane.innerHTML = `
        <div class="result-section">
          <h3 class="result-title">❓ Open Questions</h3>
          <div class="result-content">${formatResultText(result.open_questions)}</div>
        </div>`;
    }

    // Activate Smart Summary tab
    tabs.forEach(t => t.classList.remove('active'));
    panes.forEach(p => p.classList.remove('active'));
    document.getElementById('tab-smart-summary').classList.add('active');
    document.getElementById('pane-smart-summary').classList.add('active');

    // Update Aurix Score — all green
    document.querySelectorAll('.sdot').forEach(d => {
      d.classList.remove('dim');
      d.classList.add('green');
    });
  }

  function formatResultText(text) {
    return parseMarkdown(text);
  }

  function parseMarkdown(text) {
    if (!text) return '';
    let html = escapeHtml(text);
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Italic
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    // Headers
    html = html.replace(/^### (.*$)/gim, '<h4>$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^# (.*$)/gim, '<h2>$1</h2>');
    // Lists
    html = html.replace(/^\s*[-•]\s*(.*$)/gim, '<li>$1</li>');
    // Wrap lists in ul
    html = html.replace(/(<li>.*<\/li>)/s, '<ul class="result-list">$1</ul>');
    // Line breaks
    html = html.replace(/\n/g, '<br/>');
    // Clean up empty br tags inside ul
    html = html.replace(/(<\/li>)<br\/>/g, '$1');
    html = html.replace(/<br\/>(<li>)/g, '$1');
    html = html.replace(/<\/ul><br\/>/g, '</ul>');
    return html;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ═══════════════════════════════════════════════════
  //  RAG CHAT
  // ═══════════════════════════════════════════════════

  const chatInput = document.getElementById('chat-input');
  const chatSendBtn = document.getElementById('chat-send');
  const chatMessages = document.getElementById('chat-messages');

  chatSendBtn && chatSendBtn.addEventListener('click', sendChat);
  chatInput && chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChat();
    }
  });

  async function sendChat() {
    const question = chatInput ? chatInput.value.trim() : '';
    if (!question) return;

    // Add user message
    addChatMessage('You', question, 'user');
    chatInput.value = '';

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ session_id: activeSessionId, question }),
      });

      const data = await res.json();

      if (data.success) {
        addChatMessage('Aurix AI', data.answer, 'bot');
      } else {
        addChatMessage('Aurix AI', data.error || 'Could not get an answer.', 'bot');
      }
    } catch (err) {
      addChatMessage('Aurix AI', 'Server not available. Please ensure the Flask server is running.', 'bot');
    }
  }

  function addChatMessage(sender, text, type) {
    if (!chatMessages) return;

    const msg = document.createElement('div');
    msg.className = `chat-msg ${type}`;
    msg.innerHTML = `
      <span class="chat-sender">${escapeHtml(sender)}</span>
      <div class="chat-bubble">${escapeHtml(text)}</div>
    `;
    chatMessages.appendChild(msg);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // ═══════════════════════════════════════════════════
  //  SIMULATION FALLBACK (when server is offline)
  // ═══════════════════════════════════════════════════

  function simulateProcessing(source) {
    resetPipeline();

    setTimeout(() => { pipDots[0].classList.add('active'); pipelineProgress.style.width = '15%'; }, 300);
    setTimeout(() => { pipDots[1].classList.add('processing'); pipelineProgress.style.width = '40%'; }, 1200);
    setTimeout(() => { pipDots[1].classList.remove('processing'); pipDots[1].classList.add('active'); pipelineProgress.style.width = '50%'; }, 2500);
    setTimeout(() => { pipDots[2].classList.add('processing'); pipelineProgress.style.width = '70%'; }, 3000);
    setTimeout(() => { pipDots[2].classList.remove('processing'); pipDots[2].classList.add('active'); pipelineProgress.style.width = '80%'; }, 4500);
    setTimeout(() => { pipDots[3].classList.add('processing'); pipelineProgress.style.width = '92%'; }, 5000);
    setTimeout(() => {
      pipDots[3].classList.remove('processing');
      pipDots[3].classList.add('active');
      pipelineProgress.style.width = '100%';
      showNotification('Demo analysis complete!', 'success');
      displayResults({
        title: 'AI Meeting Analysis — Demo',
        summary: '• This is a demo summary showing how Aurix AI processes your content.\n• The full pipeline includes audio extraction, transcription, and AI analysis.\n• Start the Flask server and provide a real YouTube URL to see live results.\n• All processing happens locally on your machine for maximum privacy.',
        action_items: '1. Set up MISTRAL_API_KEY in .env file\n2. Install dependencies: pip install -r requirements.txt\n3. Start the server: python server.py\n4. Process a real YouTube URL or upload a file',
        key_decisions: '1. Architecture uses Flask API connecting frontend to Python AI pipeline\n2. RAG-based Q&A enabled via ChromaDB + HuggingFace embeddings\n3. Privacy-first: all processing runs locally',
        open_questions: '1. What Whisper model size gives the best speed/accuracy tradeoff?\n2. Should we add multi-language support beyond English and Hinglish?',
      });
    }, 6500);
  }

  // ═══════════════════════════════════════════════════
  //  HELPERS
  // ═══════════════════════════════════════════════════

  function resetPipeline() {
    pipDots.forEach(d => d.classList.remove('active', 'processing'));
    pipelineProgress.style.width = '0%';
  }

  function showNotification(message, type = 'info') {
    const existing = document.querySelector('.toast-notification');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    toast.setAttribute('role', 'alert');

    const colors = {
      info:    { bg: 'rgba(0,212,255,0.12)', border: 'rgba(0,212,255,0.3)', color: '#00d4ff' },
      success: { bg: 'rgba(34,211,165,0.12)', border: 'rgba(34,211,165,0.3)', color: '#22d3a5' },
      error:   { bg: 'rgba(239,68,68,0.12)',  border: 'rgba(239,68,68,0.3)',  color: '#f87171' },
    };

    const c = colors[type] || colors.info;

    toast.style.cssText = `
      position:fixed;bottom:24px;right:24px;padding:12px 20px;
      background:${c.bg};border:1px solid ${c.border};border-radius:12px;
      color:${c.color};font-family:var(--font);font-size:13px;font-weight:500;
      z-index:1000;backdrop-filter:blur(16px);box-shadow:0 8px 32px rgba(0,0,0,0.3);
      transform:translateY(20px);opacity:0;transition:transform 0.3s ease,opacity 0.3s ease;
    `;

    toast.textContent = message;
    document.body.appendChild(toast);

    requestAnimationFrame(() => {
      toast.style.transform = 'translateY(0)';
      toast.style.opacity = '1';
    });

    setTimeout(() => {
      toast.style.transform = 'translateY(20px)';
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // --- Log ---
  console.log('%c Aurix AI Dashboard ', 'background:#00d4ff;color:#000;font-weight:700;font-size:14px;padding:4px 8px;border-radius:4px;', '— Loaded ✓');

})();
