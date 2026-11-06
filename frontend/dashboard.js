// ===========================
//  Aurix AI — dashboard.js
//  Multi-Format Knowledge & Q&A (PDF, Audio, Video, Text)
// ===========================

(() => {
  'use strict';

  const API_BASE = window.location.origin;

  // --- Auth check with guest fallback ---
  let currentUser = JSON.parse(localStorage.getItem('aurix-user') || 'null');
  let sessionId = localStorage.getItem('aurix-session') || '';

  if (!currentUser) {
    currentUser = { name: "Guest User", email: "guest@aurix.ai", picture: "" };
    sessionId = 'guest_' + Math.random().toString(36).substring(2, 10);
    localStorage.setItem('aurix-user', JSON.stringify(currentUser));
    localStorage.setItem('aurix-session', sessionId);
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

  // --- Elements ---
  const browseBtn = document.getElementById('browse-btn');
  const fileInput = document.getElementById('file-input');
  const dropZone = document.getElementById('drop-zone');
  const selectedFileCard = document.getElementById('selected-file-card');
  const selectedFileIcon = document.getElementById('selected-file-icon');
  const selectedFileName = document.getElementById('selected-file-name');
  const selectedFileSize = document.getElementById('selected-file-size');
  const selectedFileBadge = document.getElementById('selected-file-badge');
  const langSelect = document.getElementById('lang-select');

  const pipelineProgress = document.getElementById('pipeline-progress');
  const pipDots = document.querySelectorAll('.pip-dot');

  const chatInput = document.getElementById('chat-input');
  const chatSendBtn = document.getElementById('chat-send');
  const chatMessages = document.getElementById('chat-messages');
  const chatStatusBadge = document.getElementById('chat-status-badge');
  const statusRagDot = document.getElementById('status-rag-dot');

  let activeSessionId = sessionId || ('aurix_' + Math.random().toString(36).substring(2, 10));
  let isContentReady = false;

  // Supported extensions
  const DOC_EXTS = ['.pdf', '.docx', '.txt', '.md', '.csv', '.rtf', '.json', '.log'];
  const AUDIO_EXTS = ['.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.wma'];
  const VIDEO_EXTS = ['.mp4', '.mov', '.mkv', '.avi', '.webm', '.flv', '.wmv'];
  const ALL_SUPPORTED = [...DOC_EXTS, ...AUDIO_EXTS, ...VIDEO_EXTS];

  // --- File input trigger ---
  browseBtn && browseBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  dropZone && dropZone.addEventListener('click', () => {
    fileInput.click();
  });

  fileInput && fileInput.addEventListener('change', (e) => {
    const files = e.target.files;
    if (files.length > 0) {
      handleSelectedFile(files[0]);
    }
  });

  // --- Drag and drop ---
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
        handleSelectedFile(files[0]);
      }
    });
  }

  function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  function getFileCategory(ext) {
    if (AUDIO_EXTS.includes(ext)) return { category: 'audio', icon: '🎙️', label: 'Audio' };
    if (VIDEO_EXTS.includes(ext)) return { category: 'video', icon: '🎬', label: 'Video' };
    if (ext === '.pdf') return { category: 'pdf', icon: '📄', label: 'PDF' };
    return { category: 'text', icon: '📝', label: 'Document' };
  }

  function handleSelectedFile(file) {
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!ALL_SUPPORTED.includes(ext)) {
      showNotification(`Unsupported file format '${ext}'. Please upload a PDF, audio, video, or text file.`, 'error');
      return;
    }

    const { icon, label } = getFileCategory(ext);

    // Show file badge
    if (selectedFileCard) {
      selectedFileCard.style.display = 'flex';
      if (selectedFileIcon) selectedFileIcon.textContent = icon;
      selectedFileName.textContent = `${file.name} (${label})`;
      selectedFileSize.textContent = formatBytes(file.size);
      selectedFileBadge.textContent = 'Processing...';
      selectedFileBadge.classList.remove('complete');
    }

    showNotification(`Selected ${file.name} — starting analysis...`, 'info');
    startRealProcessing(file);
  }

  // ═══════════════════════════════════════════════════
  //  REAL PROCESSING — Calls Flask API
  // ═══════════════════════════════════════════════════

  async function startRealProcessing(file) {
    resetPipeline();
    disableChat();

    try {
      const formData = new FormData();
      formData.append('session_id', activeSessionId);
      formData.append('file', file);
      if (langSelect) {
        formData.append('language', langSelect.value);
      }

      const res = await fetch(`${API_BASE}/api/process`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });

      const data = await res.json();

      if (!data.success) {
        showNotification(data.error || 'Failed to start processing', 'error');
        if (selectedFileBadge) selectedFileBadge.textContent = 'Error';
        return;
      }

      activeSessionId = data.session_id;
      localStorage.setItem('aurix-session', activeSessionId);

      // Start progress tracking
      pollStatus(activeSessionId);

    } catch (err) {
      console.error('Processing error:', err);
      showNotification('Server offline or network error. Please ensure Flask is running.', 'error');
    }
  }

  function pollStatus(sid) {
    let eventSource = null;
    try {
      eventSource = new EventSource(`${API_BASE}/api/status/stream/${sid}`);

      eventSource.onmessage = (event) => {
        try {
          const status = JSON.parse(event.data);
          updatePipelineUI(status);

          if (status.step === 'complete') {
            eventSource.close();
            fetchResult(sid);
          }

          if (status.step === 'error') {
            eventSource.close();
            showNotification('Error: ' + (status.detail || status.error), 'error');
            if (selectedFileBadge) selectedFileBadge.textContent = 'Error';
          }
        } catch (e) {
          console.error('SSE parse error:', e);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        pollStatusFallback(sid);
      };
    } catch {
      pollStatusFallback(sid);
    }
  }

  async function pollStatusFallback(sid) {
    let running = true;
    while (running) {
      try {
        const res = await fetch(`${API_BASE}/api/status/${sid}`);
        const status = await res.json();
        updatePipelineUI(status);

        if (status.step === 'complete') {
          running = false;
          fetchResult(sid);
        } else if (status.step === 'error') {
          running = false;
          showNotification('Error: ' + (status.detail || status.error), 'error');
          if (selectedFileBadge) selectedFileBadge.textContent = 'Error';
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
    if (pipelineProgress) {
      pipelineProgress.style.width = `${progress}%`;
    }

    const step = status.step || '';

    // Step 1: Upload / Extraction / Audio Prep
    if (['extracting', 'extracted', 'audio', 'audio_done', 'transcription', 'transcription_done', 'title', 'title_done', 'summary', 'summary_done', 'extraction', 'extraction_done', 'rag', 'rag_done', 'complete'].includes(step)) {
      setDotState(0, ['extracting', 'audio'].includes(step) ? 'processing' : 'active');
    }

    // Step 2: Speech Transcription / Document Reading
    if (['transcription', 'transcription_done', 'extracted', 'title', 'title_done', 'summary', 'summary_done', 'extraction', 'extraction_done', 'rag', 'rag_done', 'complete'].includes(step)) {
      setDotState(1, ['transcription', 'title'].includes(step) ? 'processing' : 'active');
    }

    // Step 3: Summarization & Insights
    if (['summary', 'summary_done', 'extraction', 'extraction_done', 'rag', 'rag_done', 'complete'].includes(step)) {
      setDotState(2, ['summary', 'extraction'].includes(step) ? 'processing' : 'active');
    }

    // Step 4: RAG Ready
    if (['rag', 'rag_done', 'complete'].includes(step)) {
      setDotState(3, step === 'rag' ? 'processing' : 'active');
    }

    if (status.detail) {
      showNotification(status.detail, 'info');
    }
  }

  function setDotState(index, state) {
    if (pipDots[index]) {
      pipDots[index].classList.remove('active', 'processing');
      if (state) pipDots[index].classList.add(state);
    }
  }

  async function fetchResult(sid) {
    try {
      const res = await fetch(`${API_BASE}/api/result/${sid}`);
      const data = await res.json();

      if (data.success && data.result) {
        displayResults(data.result);
        enableChat(data.result);
        showNotification('Analysis complete! Ready for interactive Q&A.', 'success');
        if (selectedFileBadge) {
          selectedFileBadge.textContent = 'Analyzed';
          selectedFileBadge.classList.add('complete');
        }
      }
    } catch (err) {
      console.error('Fetch result error:', err);
    }
  }

  // ═══════════════════════════════════════════════════
  //  DISPLAY RESULTS
  // ═══════════════════════════════════════════════════

  function displayResults(result) {
    // Update Title
    const titleEl = document.getElementById('dash-title');
    if (result.title && titleEl) {
      titleEl.textContent = result.title;
    }

    // Smart Summary Tab
    const summaryPlaceholder = document.getElementById('summary-placeholder');
    const summaryBody = document.getElementById('summary-body');

    if (summaryPlaceholder) summaryPlaceholder.style.display = 'none';
    if (summaryBody && result.summary) {
      summaryBody.style.display = 'block';
      summaryBody.innerHTML = renderMarkdown(result.summary);
    }

    // Action Items Tab
    const factPane = document.getElementById('pane-fact-check');
    if (factPane) {
      factPane.innerHTML = `
        <div class="result-section">
          <h3 class="result-title">📋 Action Items &amp; Next Steps</h3>
          <div class="result-content">${renderStructuredList(result.action_items, 'No action items identified.')}</div>
        </div>`;
    }

    // Key Findings / Decisions Tab
    const synthPane = document.getElementById('pane-synthesis');
    if (synthPane) {
      synthPane.innerHTML = `
        <div class="result-section">
          <h3 class="result-title">🔑 Key Decisions &amp; Core Findings</h3>
          <div class="result-content">${renderStructuredList(result.key_decisions, 'No key decisions identified.')}</div>
        </div>`;
    }

    // Open Questions Tab
    const verifyPane = document.getElementById('pane-verification');
    if (verifyPane) {
      verifyPane.innerHTML = `
        <div class="result-section">
          <h3 class="result-title">❓ Open Questions &amp; Challenges</h3>
          <div class="result-content">${renderStructuredList(result.open_questions, 'No open questions identified.')}</div>
        </div>`;
    }

    // Ensure Smart Summary tab is active
    tabs.forEach(t => t.classList.remove('active'));
    panes.forEach(p => p.classList.remove('active'));
    document.getElementById('tab-smart-summary')?.classList.add('active');
    document.getElementById('pane-smart-summary')?.classList.add('active');

    // Update status dots
    document.querySelectorAll('.sdot').forEach(d => {
      d.classList.remove('dim');
      d.classList.add('green');
    });
  }

  // Clean Markdown to HTML parser
  function renderMarkdown(md) {
    if (!md) return '';
    let html = md;

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h4>$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^# (.*$)/gim, '<h2>$1</h2>');

    // Bold
    html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');

    // Bullet points & numbered lists
    const lines = html.split('\n');
    let inList = false;
    let listType = 'ul';
    let result = [];

    for (let line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('•') || trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        if (!inList || listType !== 'ul') {
          if (inList) result.push(`</${listType}>`);
          result.push('<ul>');
          inList = true;
          listType = 'ul';
        }
        const text = trimmed.replace(/^[•\-*]\s*/, '');
        result.push(`<li>${text}</li>`);
      } else if (/^\d+\.\s/.test(trimmed)) {
        if (!inList || listType !== 'ol') {
          if (inList) result.push(`</${listType}>`);
          result.push('<ol>');
          inList = true;
          listType = 'ol';
        }
        const text = trimmed.replace(/^\d+\.\s*/, '');
        result.push(`<li>${text}</li>`);
      } else {
        if (inList) {
          result.push(`</${listType}>`);
          inList = false;
        }
        if (trimmed) {
          if (trimmed.startsWith('<h') || trimmed.startsWith('---')) {
            result.push(trimmed.startsWith('---') ? '<hr style="border:0;border-top:1px solid rgba(255,255,255,0.1);margin:14px 0;" />' : trimmed);
          } else {
            result.push(`<p>${trimmed}</p>`);
          }
        }
      }
    }
    if (inList) result.push(`</${listType}>`);

    return result.join('\n');
  }

  function renderStructuredList(rawText, emptyFallback) {
    if (!rawText || !rawText.trim()) {
      return `<p class="placeholder-msg">${emptyFallback}</p>`;
    }
    return renderMarkdown(rawText);
  }

  // ═══════════════════════════════════════════════════
  //  RAG CONTENT Q&A CHAT
  // ═══════════════════════════════════════════════════

  function enableChat(result) {
    isContentReady = true;
    if (chatInput) {
      chatInput.disabled = false;
      chatInput.placeholder = 'Ask anything about the uploaded file...';
    }
    if (chatSendBtn) {
      chatSendBtn.disabled = false;
    }
    if (chatStatusBadge) {
      chatStatusBadge.textContent = 'Ready for Q&A';
      chatStatusBadge.classList.add('active');
    }
    if (statusRagDot) {
      statusRagDot.classList.remove('dim');
      statusRagDot.classList.add('green');
    }

    const placeholder = document.getElementById('chat-placeholder');
    if (placeholder) {
      placeholder.innerHTML = `
        <p style="color:var(--accent-green);font-weight:500;">✓ Content indexed and ready! Ask any question below to get factual answers based on your uploaded file.</p>
      `;
    }
  }

  function disableChat() {
    isContentReady = false;
    if (chatInput) {
      chatInput.disabled = true;
      chatInput.placeholder = 'Processing content... please wait';
    }
    if (chatSendBtn) {
      chatSendBtn.disabled = true;
    }
    if (chatStatusBadge) {
      chatStatusBadge.textContent = 'Indexing...';
      chatStatusBadge.classList.remove('active');
    }
  }

  chatSendBtn && chatSendBtn.addEventListener('click', sendChat);
  chatInput && chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChat();
    }
  });

  async function sendChat() {
    if (!isContentReady) {
      showNotification('Please upload and process a file first.', 'error');
      return;
    }

    const question = chatInput ? chatInput.value.trim() : '';
    if (!question) return;

    // Add user message
    addChatMessage('You', question, 'user');
    chatInput.value = '';

    // Add temporary thinking indicator
    const thinkingId = addThinkingMessage();

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ session_id: activeSessionId, question }),
      });

      const data = await res.json();
      removeThinkingMessage(thinkingId);

      if (data.success && data.answer) {
        addChatMessage('Aurix AI', data.answer, 'bot');
      } else {
        addChatMessage('Aurix AI', data.error || 'Could not find an answer in the uploaded content.', 'bot');
      }
    } catch (err) {
      removeThinkingMessage(thinkingId);
      addChatMessage('Aurix AI', 'Failed to reach the server. Please verify the Flask server is running.', 'bot');
    }
  }

  function addChatMessage(sender, text, type) {
    if (!chatMessages) return;

    const placeholder = document.getElementById('chat-placeholder');
    if (placeholder) placeholder.style.display = 'none';

    const msg = document.createElement('div');
    msg.className = `chat-msg ${type}`;
    msg.innerHTML = `
      <span class="chat-sender">${escapeHtml(sender)}</span>
      <div class="chat-bubble">${renderMarkdown(text)}</div>
    `;
    chatMessages.appendChild(msg);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function addThinkingMessage() {
    const id = 'thinking-' + Date.now();
    const msg = document.createElement('div');
    msg.className = 'chat-msg bot';
    msg.id = id;
    msg.innerHTML = `
      <span class="chat-sender">Aurix AI</span>
      <div class="chat-bubble" style="color:var(--accent-cyan);font-style:italic;">Searching content and generating answer...</div>
    `;
    chatMessages.appendChild(msg);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
  }

  function removeThinkingMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ═══════════════════════════════════════════════════
  //  HELPERS
  // ═══════════════════════════════════════════════════

  function resetPipeline() {
    pipDots.forEach(d => d.classList.remove('active', 'processing'));
    if (pipelineProgress) pipelineProgress.style.width = '0%';
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
    }, 3500);
  }

  console.log('%c Aurix AI Multi-Format Dashboard Loaded ✓ ', 'background:#00d4ff;color:#000;font-weight:700;font-size:14px;padding:4px 8px;border-radius:4px;');

})();
