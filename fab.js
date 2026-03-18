(() => {
  if (window.__jobVaultFAB) return;
  window.__jobVaultFAB = true;

  const SHADOW_HOST_ID = 'jobvault-fab-host';

  const host = document.createElement('div');
  host.id = SHADOW_HOST_ID;
  document.body.appendChild(host);
  const shadow = host.attachShadow({ mode: 'closed' });

  const style = document.createElement('style');
  style.textContent = `
    .jv-fab {
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 2147483647;
      width: 52px;
      height: 52px;
      border-radius: 50%;
      background: #2563eb;
      color: #fff;
      border: none;
      cursor: pointer;
      box-shadow: 0 4px 16px rgba(37,99,235,0.35);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 22px;
      font-weight: 700;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      transition: transform 0.2s, box-shadow 0.2s, background 0.2s;
      line-height: 1;
    }
    .jv-fab:hover {
      transform: scale(1.08);
      box-shadow: 0 6px 24px rgba(37,99,235,0.45);
      background: #1d4ed8;
    }
    .jv-fab:active { transform: scale(0.95); }
    .jv-fab.saved {
      background: #10b981;
      box-shadow: 0 4px 16px rgba(16,185,129,0.35);
    }
    .jv-fab.saving {
      opacity: 0.7;
      pointer-events: none;
    }
    .jv-toast {
      position: fixed;
      bottom: 86px;
      right: 24px;
      z-index: 2147483647;
      background: #1e293b;
      color: #fff;
      padding: 10px 16px;
      border-radius: 8px;
      font-size: 13px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      box-shadow: 0 8px 24px rgba(0,0,0,0.2);
      opacity: 0;
      transform: translateY(8px);
      transition: opacity 0.2s, transform 0.2s;
    }
    .jv-toast.visible {
      opacity: 1;
      transform: translateY(0);
    }
  `;
  shadow.appendChild(style);

  const fab = document.createElement('button');
  fab.className = 'jv-fab';
  fab.textContent = 'JV';
  fab.title = 'Save to JobVault';
  shadow.appendChild(fab);

  const toast = document.createElement('div');
  toast.className = 'jv-toast';
  shadow.appendChild(toast);

  function showToast(msg, duration = 2500) {
    toast.textContent = msg;
    toast.classList.add('visible');
    setTimeout(() => toast.classList.remove('visible'), duration);
  }

  function getText(selectors) {
    for (const sel of selectors) {
      try {
        const el = document.querySelector(sel);
        if (el) {
          const text = el.innerText?.trim();
          if (text) return text;
        }
      } catch {}
    }
    return '';
  }

  function getMetaContent(property) {
    const meta =
      document.querySelector(`meta[property="${property}"]`) ||
      document.querySelector(`meta[name="${property}"]`);
    return meta?.getAttribute('content')?.trim() || '';
  }

  function quickExtract() {
    const title =
      getText(['h1', '[class*="title" i]']) || getMetaContent('og:title') || document.title;
    const company =
      getMetaContent('og:site_name') || getText(['[class*="company" i]', '[class*="employer" i]']);
    const location = getText(['[class*="location" i]']);
    const description = getText([
      '[class*="description" i]', 'article', 'main', '#content',
    ]) || '';

    return {
      title: title.substring(0, 200),
      company: company.substring(0, 100),
      location: location.substring(0, 100),
      description: description.substring(0, 3000),
      url: window.location.href,
    };
  }

  fab.addEventListener('click', async () => {
    fab.classList.add('saving');
    try {
      const data = quickExtract();
      const now = new Date().toISOString();

      const job = {
        id: crypto.randomUUID(),
        title: data.title,
        company: data.company,
        location: data.location,
        salary: '',
        url: data.url,
        description: data.description,
        status: 'Saved',
        notes: '',
        tags: [],
        reminderDate: null,
        applyUrl: '',
        timeline: [{ date: now, event: 'Saved via quick-save button', type: 'manual' }],
        autoStatus: 'active',
        lastChecked: null,
        dateSaved: now,
        lastUpdated: now,
      };

      const { jobs = [] } = await chrome.storage.local.get('jobs');

      const dup = jobs.findIndex((j) => j.url === job.url && job.url);
      if (dup !== -1) {
        showToast('Already saved! Open extension popup to edit.');
        fab.classList.remove('saving');
        return;
      }

      jobs.push(job);
      await chrome.storage.local.set({ jobs });

      fab.classList.remove('saving');
      fab.classList.add('saved');
      fab.textContent = '\u2713';
      showToast('Saved to JobVault!');

      setTimeout(() => {
        fab.classList.remove('saved');
        fab.textContent = 'JV';
      }, 3000);
    } catch (err) {
      fab.classList.remove('saving');
      showToast('Error saving: ' + err.message);
    }
  });
})();
