document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('searchInput');
  const statusFilter = document.getElementById('statusFilter');
  const tagFilter = document.getElementById('tagFilter');
  const jobsBody = document.getElementById('jobsBody');
  const jobCount = document.getElementById('jobCount');
  const emptyState = document.getElementById('emptyState');
  const tableWrapper = document.getElementById('tableWrapper');
  const kanbanView = document.getElementById('kanbanView');
  const statsBar = document.getElementById('statsBar');

  const editModal = document.getElementById('editModal');
  const editForm = document.getElementById('editForm');
  const deleteModal = document.getElementById('deleteModal');
  const timelineModal = document.getElementById('timelineModal');
  const settingsModal = document.getElementById('settingsModal');

  let allJobs = [];
  let pendingDeleteId = null;
  let currentView = 'table';
  let sortCol = 'dateSaved';
  let sortDir = 'desc';

  /* ── Dark Mode ─────────────────────────────────────── */

  async function initDarkMode() {
    const { settings } = await chrome.storage.local.get('settings');
    const pref = settings?.darkMode || 'auto';
    applyDarkMode(pref);
  }

  function applyDarkMode(pref) {
    const dark =
      pref === 'dark' ||
      (pref === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.body.classList.toggle('dark', dark);
    document.getElementById('darkIcon').textContent = dark ? '\u2600' : '\u263E';
  }

  document.getElementById('darkToggle').addEventListener('click', async () => {
    const isDark = document.body.classList.contains('dark');
    const next = isDark ? 'light' : 'dark';
    applyDarkMode(next);
    const { settings = {} } = await chrome.storage.local.get('settings');
    settings.darkMode = next;
    await chrome.storage.local.set({ settings });
  });

  /* ── Load & Render ─────────────────────────────────── */

  async function loadJobs() {
    const { jobs = [] } = await chrome.storage.local.get('jobs');
    allJobs = jobs;
    populateTagFilter();
    renderAll();
  }

  function getFiltered() {
    const query = searchInput.value.toLowerCase().trim();
    const status = statusFilter.value;
    const tag = tagFilter.value;

    return allJobs
      .filter((job) => {
        const matchesStatus = !status || job.status === status;
        const matchesTag = !tag || (job.tags && job.tags.includes(tag));
        const matchesSearch =
          !query ||
          job.title?.toLowerCase().includes(query) ||
          job.company?.toLowerCase().includes(query) ||
          job.notes?.toLowerCase().includes(query) ||
          job.tags?.some((t) => t.toLowerCase().includes(query));
        return matchesStatus && matchesSearch && matchesTag;
      })
      .sort((a, b) => {
        let aVal = a[sortCol] || '';
        let bVal = b[sortCol] || '';
        if (sortCol === 'dateSaved' || sortCol === 'lastUpdated') {
          aVal = new Date(aVal || 0).getTime();
          bVal = new Date(bVal || 0).getTime();
        } else {
          aVal = String(aVal).toLowerCase();
          bVal = String(bVal).toLowerCase();
        }
        if (aVal < bVal) return sortDir === 'asc' ? -1 : 1;
        if (aVal > bVal) return sortDir === 'asc' ? 1 : -1;
        return 0;
      });
  }

  function renderAll() {
    const filtered = getFiltered();
    jobCount.textContent = `${filtered.length} job${filtered.length !== 1 ? 's' : ''}`;
    renderStats();

    if (filtered.length === 0) {
      emptyState.classList.remove('hidden');
      tableWrapper.classList.add('hidden');
      kanbanView.classList.add('hidden');
      return;
    }

    emptyState.classList.add('hidden');

    if (currentView === 'table') {
      tableWrapper.classList.remove('hidden');
      kanbanView.classList.add('hidden');
      renderTable(filtered);
    } else {
      tableWrapper.classList.add('hidden');
      kanbanView.classList.remove('hidden');
      renderKanban(filtered);
    }
  }

  /* ── Stats Bar ─────────────────────────────────────── */

  function renderStats() {
    const counts = {};
    const statuses = ['Saved', 'Applied', 'Interview', 'Offer', 'Rejected'];
    statuses.forEach((s) => (counts[s] = 0));
    allJobs.forEach((j) => {
      if (counts[j.status] !== undefined) counts[j.status]++;
    });
    const total = allJobs.length || 1;

    statsBar.innerHTML = `
      <div class="stats-segments">
        ${statuses
          .map(
            (s) => `
          <div class="stat-segment stat-${s.toLowerCase()}" style="flex:${counts[s] / total}" title="${s}: ${counts[s]}">
            ${counts[s] > 0 ? counts[s] : ''}
          </div>`
          )
          .join('')}
      </div>
      <div class="stats-legend">
        ${statuses
          .map(
            (s) =>
              `<span class="legend-item"><span class="legend-dot legend-${s.toLowerCase()}"></span>${s} (${counts[s]})</span>`
          )
          .join('')}
      </div>`;
  }

  /* ── Table View ────────────────────────────────────── */

  function renderTable(filtered) {
    jobsBody.innerHTML = filtered
      .map(
        (job) => `
      <tr data-id="${job.id}">
        <td>
          ${
            job.url
              ? `<a href="${esc(job.url)}" target="_blank" title="${esc(job.title)}">${esc(job.title || '(untitled)')}</a>`
              : esc(job.title || '(untitled)')
          }
          ${job.autoStatus === 'closed' ? '<span class="auto-badge">Closed</span>' : ''}
        </td>
        <td>${esc(job.company || '\u2014')}</td>
        <td>${esc(job.location || '\u2014')}</td>
        <td class="salary-cell">${esc(job.salary || '\u2014')}</td>
        <td>
          <span class="status-badge status-${(job.status || 'saved').toLowerCase()}">
            ${esc(job.status || 'Saved')}
          </span>
        </td>
        <td class="tags-cell">${(job.tags || []).map((t) => `<span class="mini-tag">${esc(t)}</span>`).join('')}</td>
        <td class="date-cell">${formatDate(job.dateSaved)}</td>
        <td class="date-cell">${formatDate(job.lastUpdated)}</td>
        <td class="action-cell">
          <button class="btn-icon timeline-btn" data-id="${job.id}" title="Timeline">&#128337;</button>
          <button class="btn-icon edit" data-id="${job.id}" title="Edit">&#9998;</button>
          <button class="btn-icon delete" data-id="${job.id}" title="Delete">&#10005;</button>
        </td>
      </tr>`
      )
      .join('');
  }

  /* ── Kanban View ───────────────────────────────────── */

  function renderKanban(filtered) {
    const statuses = ['Saved', 'Applied', 'Interview', 'Offer', 'Rejected'];
    statuses.forEach((status) => {
      const container = kanbanView.querySelector(`.kanban-cards[data-status="${status}"]`);
      const countEl = kanbanView.querySelector(`.kanban-count[data-count="${status}"]`);
      const cards = filtered.filter((j) => j.status === status);
      countEl.textContent = cards.length;

      container.innerHTML = cards
        .map(
          (job) => `
        <div class="kanban-card" draggable="true" data-id="${job.id}">
          <div class="kc-title">${esc(job.title || '(untitled)')}</div>
          <div class="kc-company">${esc(job.company || '')}</div>
          ${job.salary ? `<div class="kc-salary">${esc(job.salary)}</div>` : ''}
          ${job.location ? `<div class="kc-location">${esc(job.location)}</div>` : ''}
          <div class="kc-tags">${(job.tags || []).map((t) => `<span class="mini-tag">${esc(t)}</span>`).join('')}</div>
          ${job.autoStatus === 'closed' ? '<span class="auto-badge">Listing closed</span>' : ''}
          <div class="kc-actions">
            <button class="btn-icon timeline-btn" data-id="${job.id}" title="Timeline">&#128337;</button>
            <button class="btn-icon edit" data-id="${job.id}" title="Edit">&#9998;</button>
            <button class="btn-icon delete" data-id="${job.id}" title="Delete">&#10005;</button>
          </div>
        </div>`
        )
        .join('');
    });

    initDragDrop();
  }

  /* ── Drag & Drop ───────────────────────────────────── */

  function initDragDrop() {
    kanbanView.querySelectorAll('.kanban-card').forEach((card) => {
      card.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('text/plain', card.dataset.id);
        card.classList.add('dragging');
      });
      card.addEventListener('dragend', () => card.classList.remove('dragging'));
    });

    kanbanView.querySelectorAll('.kanban-cards').forEach((col) => {
      col.addEventListener('dragover', (e) => {
        e.preventDefault();
        col.classList.add('drag-over');
      });
      col.addEventListener('dragleave', () => col.classList.remove('drag-over'));
      col.addEventListener('drop', async (e) => {
        e.preventDefault();
        col.classList.remove('drag-over');
        const jobId = e.dataTransfer.getData('text/plain');
        const newStatus = col.dataset.status;
        const job = allJobs.find((j) => j.id === jobId);
        if (job && job.status !== newStatus) {
          const oldStatus = job.status;
          job.status = newStatus;
          job.lastUpdated = new Date().toISOString();
          if (!job.timeline) job.timeline = [];
          job.timeline.push({
            date: job.lastUpdated,
            event: `Status changed from ${oldStatus} to ${newStatus}`,
            type: 'manual',
          });
          await chrome.storage.local.set({ jobs: allJobs });
          renderAll();
        }
      });
    });
  }

  /* ── Sorting ───────────────────────────────────────── */

  document.querySelectorAll('th.sortable').forEach((th) => {
    th.addEventListener('click', () => {
      const col = th.dataset.sort;
      if (sortCol === col) {
        sortDir = sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        sortCol = col;
        sortDir = 'asc';
      }
      document.querySelectorAll('.sort-arrow').forEach((a) => (a.textContent = ''));
      th.querySelector('.sort-arrow').textContent = sortDir === 'asc' ? ' \u25B2' : ' \u25BC';
      renderAll();
    });
  });

  /* ── View Toggle ───────────────────────────────────── */

  document.querySelectorAll('.view-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.view-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      currentView = btn.dataset.view;
      renderAll();
    });
  });

  /* ── Search & Filter ───────────────────────────────── */

  searchInput.addEventListener('input', renderAll);
  statusFilter.addEventListener('change', renderAll);
  tagFilter.addEventListener('change', renderAll);

  function populateTagFilter() {
    const tags = new Set();
    allJobs.forEach((j) => (j.tags || []).forEach((t) => tags.add(t)));
    const current = tagFilter.value;
    tagFilter.innerHTML = '<option value="">All Tags</option>';
    [...tags].sort().forEach((t) => {
      const opt = document.createElement('option');
      opt.value = t;
      opt.textContent = t;
      tagFilter.appendChild(opt);
    });
    tagFilter.value = current;
  }

  /* ── Edit ───────────────────────────────────────────── */

  function delegateClick(parent, selector, handler) {
    parent.addEventListener('click', (e) => {
      const el = e.target.closest(selector);
      if (el) handler(el);
    });
  }

  delegateClick(document.body, '.edit', (el) => openEditModal(el.dataset.id));
  delegateClick(document.body, '.delete', (el) => openDeleteModal(el.dataset.id));
  delegateClick(document.body, '.timeline-btn', (el) => openTimelineModal(el.dataset.id));

  function openEditModal(id) {
    const job = allJobs.find((j) => j.id === id);
    if (!job) return;
    document.getElementById('editId').value = job.id;
    document.getElementById('editTitle').value = job.title || '';
    document.getElementById('editCompany').value = job.company || '';
    document.getElementById('editLocation').value = job.location || '';
    document.getElementById('editSalary').value = job.salary || '';
    document.getElementById('editUrl').value = job.url || '';
    document.getElementById('editDescription').value = job.description || '';
    document.getElementById('editStatus').value = job.status || 'Saved';
    document.getElementById('editReminder').value = job.reminderDate || '';
    document.getElementById('editTags').value = (job.tags || []).join(', ');
    document.getElementById('editNotes').value = job.notes || '';
    editModal.classList.remove('hidden');
  }

  function closeEditModal() { editModal.classList.add('hidden'); }

  editForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('editId').value;
    const idx = allJobs.findIndex((j) => j.id === id);
    if (idx === -1) return;

    const oldStatus = allJobs[idx].status;
    const newStatus = document.getElementById('editStatus').value;
    const now = new Date().toISOString();

    allJobs[idx] = {
      ...allJobs[idx],
      title: document.getElementById('editTitle').value.trim(),
      company: document.getElementById('editCompany').value.trim(),
      location: document.getElementById('editLocation').value.trim(),
      salary: document.getElementById('editSalary').value.trim(),
      url: document.getElementById('editUrl').value.trim(),
      description: document.getElementById('editDescription').value.trim(),
      status: newStatus,
      reminderDate: document.getElementById('editReminder').value || null,
      tags: document
        .getElementById('editTags')
        .value.split(',')
        .map((t) => t.trim())
        .filter(Boolean),
      notes: document.getElementById('editNotes').value.trim(),
      lastUpdated: now,
    };

    if (!allJobs[idx].timeline) allJobs[idx].timeline = [];
    if (oldStatus !== newStatus) {
      allJobs[idx].timeline.push({
        date: now,
        event: `Status changed from ${oldStatus} to ${newStatus}`,
        type: 'manual',
      });
    } else {
      allJobs[idx].timeline.push({ date: now, event: 'Job edited', type: 'manual' });
    }

    const reminder = document.getElementById('editReminder').value;
    if (reminder) {
      chrome.runtime.sendMessage({ action: 'setReminder', jobId: id, date: reminder });
    }

    await chrome.storage.local.set({ jobs: allJobs });
    closeEditModal();
    populateTagFilter();
    renderAll();
  });

  document.getElementById('modalClose').addEventListener('click', closeEditModal);
  document.getElementById('editCancel').addEventListener('click', closeEditModal);

  /* ── Delete ────────────────────────────────────────── */

  function openDeleteModal(id) {
    const job = allJobs.find((j) => j.id === id);
    if (!job) return;
    pendingDeleteId = id;
    document.getElementById('deleteJobName').textContent =
      `${job.title || 'this job'}${job.company ? ' at ' + job.company : ''}`;
    deleteModal.classList.remove('hidden');
  }

  function closeDeleteModal() {
    deleteModal.classList.add('hidden');
    pendingDeleteId = null;
  }

  document.getElementById('deleteConfirm').addEventListener('click', async () => {
    if (!pendingDeleteId) return;
    allJobs = allJobs.filter((j) => j.id !== pendingDeleteId);
    await chrome.storage.local.set({ jobs: allJobs });
    closeDeleteModal();
    populateTagFilter();
    renderAll();
  });

  document.getElementById('deleteCancel').addEventListener('click', closeDeleteModal);
  document.getElementById('deleteModalClose').addEventListener('click', closeDeleteModal);

  /* ── Timeline ──────────────────────────────────────── */

  function openTimelineModal(id) {
    const job = allJobs.find((j) => j.id === id);
    if (!job) return;
    const events = (job.timeline || []).slice().reverse();
    const content = document.getElementById('timelineContent');

    if (events.length === 0) {
      content.innerHTML = '<p class="muted">No activity recorded yet.</p>';
    } else {
      content.innerHTML = events
        .map(
          (ev) => `
        <div class="tl-item tl-${ev.type || 'manual'}">
          <div class="tl-dot"></div>
          <div class="tl-body">
            <div class="tl-event">${esc(ev.event)}</div>
            <div class="tl-date">${new Date(ev.date).toLocaleString()}</div>
          </div>
        </div>`
        )
        .join('');
    }

    timelineModal.classList.remove('hidden');
  }

  document.getElementById('timelineClose').addEventListener('click', () => {
    timelineModal.classList.add('hidden');
  });

  /* ── Settings ──────────────────────────────────────── */

  document.getElementById('settingsToggle').addEventListener('click', async () => {
    const { settings = {} } = await chrome.storage.local.get('settings');
    document.getElementById('settingsInterval').value = settings.checkIntervalHours || 6;
    document.getElementById('settingsNotifications').checked = settings.notificationsEnabled !== false;
    settingsModal.classList.remove('hidden');
  });

  document.getElementById('settingsClose').addEventListener('click', () => {
    settingsModal.classList.add('hidden');
  });

  document.getElementById('settingsInterval').addEventListener('change', async (e) => {
    const { settings = {} } = await chrome.storage.local.get('settings');
    settings.checkIntervalHours = Number(e.target.value);
    chrome.runtime.sendMessage({ action: 'saveSettings', settings });
  });

  document.getElementById('settingsNotifications').addEventListener('change', async (e) => {
    const { settings = {} } = await chrome.storage.local.get('settings');
    settings.notificationsEnabled = e.target.checked;
    chrome.runtime.sendMessage({ action: 'saveSettings', settings });
  });

  document.getElementById('checkNowBtn').addEventListener('click', () => {
    const msgEl = document.getElementById('settingsMsg');
    msgEl.textContent = 'Checking all jobs...';
    msgEl.classList.remove('hidden');
    chrome.runtime.sendMessage({ action: 'checkNow' }, () => {
      msgEl.textContent = 'Check complete!';
      setTimeout(() => {
        msgEl.classList.add('hidden');
        loadJobs();
      }, 1500);
    });
  });

  /* ── Cloud Backup / Restore ────────────────────────── */

  document.getElementById('backupBtn').addEventListener('click', () => {
    chrome.runtime.sendMessage({ action: 'backupToSync' }, (resp) => {
      if (resp?.success) {
        showToast('Backed up to Chrome Sync!');
      } else {
        showToast('Backup failed: ' + (resp?.error || 'unknown error'), true);
      }
    });
  });

  document.getElementById('restoreBtn').addEventListener('click', () => {
    chrome.runtime.sendMessage({ action: 'restoreFromSync' }, (resp) => {
      const msgEl = document.getElementById('settingsMsg');
      if (resp?.success) {
        msgEl.textContent = `Restored ${resp.count} new job(s)!`;
        msgEl.classList.remove('hidden');
        loadJobs();
      } else {
        msgEl.textContent = 'Restore failed: ' + (resp?.error || 'unknown error');
        msgEl.classList.remove('hidden');
      }
      setTimeout(() => msgEl.classList.add('hidden'), 3000);
    });
  });

  /* ── CSV Export ────────────────────────────────────── */

  document.getElementById('exportBtn').addEventListener('click', () => {
    if (allJobs.length === 0) return;
    const headers = ['Title', 'Company', 'Location', 'Salary', 'Status', 'Tags', 'URL', 'Notes', 'Date Saved', 'Last Updated'];
    const rows = allJobs.map((j) => [
      csvEsc(j.title), csvEsc(j.company), csvEsc(j.location), csvEsc(j.salary),
      csvEsc(j.status), csvEsc((j.tags || []).join('; ')), csvEsc(j.url),
      csvEsc(j.notes), csvEsc(formatDate(j.dateSaved)), csvEsc(formatDate(j.lastUpdated)),
    ]);
    const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    downloadFile(csv, `jobvault-export-${dateStamp()}.csv`, 'text/csv;charset=utf-8;');
  });

  /* ── Import ────────────────────────────────────────── */

  document.getElementById('importBtn').addEventListener('click', () => {
    document.getElementById('importFile').click();
  });

  document.getElementById('importFile').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const text = await file.text();
    let imported = [];

    if (file.name.endsWith('.json')) {
      try {
        const data = JSON.parse(text);
        imported = Array.isArray(data) ? data : data.jobs || [];
      } catch {
        showToast('Invalid JSON file', true);
        return;
      }
    } else {
      imported = parseCSV(text);
    }

    const { jobs = [] } = await chrome.storage.local.get('jobs');
    let added = 0;

    for (const item of imported) {
      const exists = jobs.some(
        (j) => (j.url && j.url === item.url) || (j.id && j.id === item.id)
      );
      if (!exists) {
        const now = new Date().toISOString();
        jobs.push({
          id: item.id || crypto.randomUUID(),
          title: item.title || item.Title || '',
          company: item.company || item.Company || '',
          location: item.location || item.Location || '',
          salary: item.salary || item.Salary || '',
          url: item.url || item.URL || '',
          description: item.description || '',
          status: item.status || item.Status || 'Saved',
          notes: item.notes || item.Notes || '',
          tags: item.tags || (item.Tags ? item.Tags.split(';').map((t) => t.trim()).filter(Boolean) : []),
          timeline: item.timeline || [{ date: now, event: 'Imported', type: 'manual' }],
          autoStatus: 'active',
          lastChecked: null,
          dateSaved: item.dateSaved || now,
          lastUpdated: now,
        });
        added++;
      }
    }

    await chrome.storage.local.set({ jobs });
    allJobs = jobs;
    populateTagFilter();
    renderAll();
    showToast(`Imported ${added} job(s)`);
    e.target.value = '';
  });

  function parseCSV(text) {
    const lines = text.split('\n').filter((l) => l.trim());
    if (lines.length < 2) return [];
    const headers = parseCSVLine(lines[0]);
    return lines.slice(1).map((line) => {
      const vals = parseCSVLine(line);
      const obj = {};
      headers.forEach((h, i) => (obj[h.trim()] = (vals[i] || '').trim()));
      return obj;
    });
  }

  function parseCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (inQuotes) {
        if (ch === '"' && line[i + 1] === '"') {
          current += '"';
          i++;
        } else if (ch === '"') {
          inQuotes = false;
        } else {
          current += ch;
        }
      } else {
        if (ch === '"') {
          inQuotes = true;
        } else if (ch === ',') {
          result.push(current);
          current = '';
        } else {
          current += ch;
        }
      }
    }
    result.push(current);
    return result;
  }

  /* ── Close modals on overlay click ─────────────────── */

  [editModal, deleteModal, timelineModal, settingsModal].forEach((m) => {
    m.addEventListener('click', (e) => {
      if (e.target === m) m.classList.add('hidden');
    });
  });

  /* ── Toast ─────────────────────────────────────────── */

  function showToast(msg, isError) {
    const toast = document.createElement('div');
    toast.className = `floating-toast ${isError ? 'toast-error' : ''}`;
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  /* ── Utilities ─────────────────────────────────────── */

  function formatDate(iso) {
    if (!iso) return '\u2014';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function esc(str) {
    if (!str) return '';
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
  }

  function csvEsc(str) {
    if (!str) return '""';
    return `"${str.replace(/"/g, '""')}"`;
  }

  function dateStamp() {
    return new Date().toISOString().slice(0, 10);
  }

  function downloadFile(content, name, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  }

  /* ── Init ──────────────────────────────────────────── */

  initDarkMode();
  loadJobs();
});
