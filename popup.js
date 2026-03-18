document.addEventListener('DOMContentLoaded', async () => {
  const form = document.getElementById('jobForm');
  const loading = document.getElementById('loading');
  const errorEl = document.getElementById('error');
  const saveMsg = document.getElementById('saveMsg');
  const authSection = document.getElementById('authSection');

  const fields = {
    title: document.getElementById('title'),
    company: document.getElementById('company'),
    location: document.getElementById('location'),
    salary: document.getElementById('salary'),
    url: document.getElementById('url'),
    description: document.getElementById('description'),
    status: document.getElementById('status'),
    reminderDate: document.getElementById('reminderDate'),
    notes: document.getElementById('notes'),
  };

  let currentTags = [];
  const tagsList = document.getElementById('tagsList');
  const tagInput = document.getElementById('tagInput');

  /* ── Auth State ──────────────────────────────────────── */

  const authToggle = document.getElementById('authToggle');
  const authForm = document.getElementById('authForm');
  const authEmail = document.getElementById('authEmail');
  const authPassword = document.getElementById('authPassword');
  const authSubmit = document.getElementById('authSubmit');
  const authSwitch = document.getElementById('authSwitch');
  const authError = document.getElementById('authError');
  const authStatus = document.getElementById('authStatus');
  const logoutBtn = document.getElementById('logoutBtn');
  let authMode = 'login';

  async function updateAuthUI() {
    const loggedIn = await API.isAuthenticated();
    if (loggedIn) {
      const config = await API.getConfig();
      authStatus.textContent = 'Synced';
      authStatus.className = 'auth-badge auth-ok';
      authForm.classList.add('hidden');
      logoutBtn.classList.remove('hidden');
    } else {
      authStatus.textContent = 'Local only';
      authStatus.className = 'auth-badge';
      logoutBtn.classList.add('hidden');
    }
  }

  authToggle.addEventListener('click', () => {
    authForm.classList.toggle('hidden');
  });

  authSwitch.addEventListener('click', () => {
    authMode = authMode === 'login' ? 'register' : 'login';
    authSubmit.textContent = authMode === 'login' ? 'Log In' : 'Sign Up';
    authSwitch.textContent = authMode === 'login' ? 'Need an account? Sign up' : 'Have an account? Log in';
    authError.classList.add('hidden');
  });

  authSubmit.addEventListener('click', async () => {
    authError.classList.add('hidden');
    const email = authEmail.value.trim();
    const password = authPassword.value.trim();
    if (!email || !password) {
      authError.textContent = 'Email and password required';
      authError.classList.remove('hidden');
      return;
    }
    try {
      if (authMode === 'register') {
        await API.register(email, password);
      }
      await API.login(email, password);
      authForm.classList.add('hidden');
      updateAuthUI();
    } catch (err) {
      authError.textContent = err.message;
      authError.classList.remove('hidden');
    }
  });

  logoutBtn.addEventListener('click', async () => {
    await API.logout();
    updateAuthUI();
  });

  updateAuthUI();

  /* ── Tag Management ────────────────────────────────── */

  function renderTags() {
    tagsList.innerHTML = currentTags
      .map(
        (tag) =>
          `<span class="tag-chip">${esc(tag)}<button type="button" class="tag-remove" data-tag="${esc(tag)}">\u00d7</button></span>`
      )
      .join('');
  }

  function addTag(tag) {
    const t = tag.trim();
    if (t && !currentTags.includes(t)) {
      currentTags.push(t);
      renderTags();
    }
  }

  function removeTag(tag) {
    currentTags = currentTags.filter((t) => t !== tag);
    renderTags();
  }

  tagInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag(tagInput.value.replace(',', ''));
      tagInput.value = '';
    }
    if (e.key === 'Backspace' && !tagInput.value && currentTags.length) {
      removeTag(currentTags[currentTags.length - 1]);
    }
  });

  tagsList.addEventListener('click', (e) => {
    const btn = e.target.closest('.tag-remove');
    if (btn) removeTag(btn.dataset.tag);
  });

  document.getElementById('tagSuggestions').addEventListener('click', (e) => {
    const btn = e.target.closest('.tag-sug');
    if (btn) addTag(btn.dataset.tag);
  });

  /* ── Extract job data from the active tab ────────── */

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab?.id || tab.url?.startsWith('chrome://') || tab.url?.startsWith('chrome-extension://')) {
      throw new Error('Cannot access this page.');
    }

    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['content.js'],
    });

    const response = await chrome.tabs.sendMessage(tab.id, { action: 'extractJob' });

    if (response?.success && response.data) {
      fields.title.value = response.data.title || '';
      fields.company.value = response.data.company || '';
      fields.location.value = response.data.location || '';
      fields.salary.value = response.data.salary || '';
      fields.url.value = response.data.url || tab.url;
      fields.description.value = truncate(response.data.description, 3000);
    } else {
      fields.url.value = tab.url;
      showError('Could not auto-detect job data. Fill in the fields manually.');
    }
  } catch {
    showError('Cannot extract from this page. You can still fill in fields manually.');

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab?.url) fields.url.value = tab.url;
    } catch { /* ignore */ }
  } finally {
    loading.classList.add('hidden');
    form.classList.remove('hidden');
    authSection.classList.remove('hidden');
  }

  /* ── Save handler ──────────────────────────────────── */

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const now = new Date().toISOString();
    const job = {
      id: crypto.randomUUID(),
      title: fields.title.value.trim(),
      company: fields.company.value.trim(),
      location: fields.location.value.trim(),
      salary: fields.salary.value.trim(),
      url: fields.url.value.trim(),
      description: fields.description.value.trim(),
      status: fields.status.value,
      notes: fields.notes.value.trim(),
      tags: [...currentTags],
      reminderDate: fields.reminderDate.value || null,
      applyUrl: '',
      timeline: [{ date: now, event: 'Job saved', type: 'manual' }],
      autoStatus: 'active',
      lastChecked: null,
      dateSaved: now,
      lastUpdated: now,
    };

    if (!job.title && !job.company) {
      showError('Please provide at least a job title or company name.');
      return;
    }

    errorEl.classList.add('hidden');

    // Always save to local storage
    const { jobs = [] } = await chrome.storage.local.get('jobs');

    const existingIndex = jobs.findIndex((j) => j.url === job.url && job.url);
    if (existingIndex !== -1) {
      const existing = jobs[existingIndex];
      jobs[existingIndex] = {
        ...existing,
        ...job,
        id: existing.id,
        dateSaved: existing.dateSaved,
        timeline: [
          ...(existing.timeline || []),
          { date: now, event: 'Job updated', type: 'manual' },
        ],
        lastUpdated: now,
      };
    } else {
      jobs.push(job);
    }

    await chrome.storage.local.set({ jobs });

    // Also sync to API if authenticated
    const loggedIn = await API.isAuthenticated();
    if (loggedIn) {
      try {
        await API.createJob({
          title: job.title,
          company: job.company,
          location: job.location,
          salary: job.salary,
          url: job.url,
          description: job.description,
          status: job.status,
          notes: job.notes,
          tags: job.tags,
          reminder_date: job.reminderDate,
          apply_url: job.applyUrl,
          timeline: job.timeline,
        });
      } catch {
        // API save failed — local copy is still safe
      }
    }

    if (job.reminderDate) {
      chrome.runtime.sendMessage({
        action: 'setReminder',
        jobId: existingIndex !== -1 ? jobs[existingIndex].id : job.id,
        date: job.reminderDate,
      });
    }

    saveMsg.classList.remove('hidden');
    setTimeout(() => saveMsg.classList.add('hidden'), 2500);
  });

  /* ── View Saved Jobs ───────────────────────────────── */

  document.getElementById('viewBtn').addEventListener('click', () => {
    chrome.tabs.create({ url: chrome.runtime.getURL('jobs.html') });
  });

  /* ── Utilities ─────────────────────────────────────── */

  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.classList.remove('hidden');
  }

  function truncate(str, max) {
    if (!str) return '';
    return str.length > max ? str.substring(0, max) + '\u2026' : str;
  }

  function esc(str) {
    if (!str) return '';
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
  }
});
