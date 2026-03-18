const CHECK_ALARM = 'jobvault-check';
const REMINDER_PREFIX = 'jobvault-reminder-';
const DEFAULT_INTERVAL_HOURS = 6;

const CLOSED_SIGNALS = [
  'no longer accepting',
  'position has been filled',
  'this job has expired',
  'job is no longer available',
  'this position is closed',
  'posting has been removed',
  'this listing has closed',
  'application deadline has passed',
  'job has been removed',
  'no longer listed',
  'this job is closed',
  'sorry, this job has been filled',
];

/* ── Install / Startup ────────────────────────────────── */

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get(['jobs', 'settings'], ({ jobs, settings }) => {
    if (!jobs) chrome.storage.local.set({ jobs: [] });
    if (!settings) {
      chrome.storage.local.set({
        settings: {
          darkMode: 'auto',
          checkIntervalHours: DEFAULT_INTERVAL_HOURS,
          notificationsEnabled: true,
        },
      });
    }
  });
  setupAlarm();
});

chrome.runtime.onStartup.addListener(() => {
  setupAlarm();
});

async function setupAlarm() {
  const { settings } = await chrome.storage.local.get('settings');
  const hours = settings?.checkIntervalHours || DEFAULT_INTERVAL_HOURS;
  chrome.alarms.create(CHECK_ALARM, {
    delayInMinutes: 1,
    periodInMinutes: hours * 60,
  });
}

/* ── Alarm Handler ────────────────────────────────────── */

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === CHECK_ALARM) {
    await checkAllJobs();
  }
  if (alarm.name.startsWith(REMINDER_PREFIX)) {
    const jobId = alarm.name.replace(REMINDER_PREFIX, '');
    await handleReminder(jobId);
  }
});

/* ── Auto Progress Tracking ───────────────────────────── */

async function checkAllJobs() {
  const { jobs = [], settings } = await chrome.storage.local.get([
    'jobs',
    'settings',
  ]);
  const trackable = ['Saved', 'Applied', 'Interview'];
  const toCheck = jobs.filter((j) => j.url && trackable.includes(j.status));
  let changed = false;

  for (const job of toCheck) {
    try {
      const result = await checkJobUrl(job.url);
      const now = new Date().toISOString();
      job.lastChecked = now;
      if (!job.timeline) job.timeline = [];

      if (result.isClosed && job.autoStatus !== 'closed') {
        job.autoStatus = 'closed';
        job.timeline.push({
          date: now,
          event: `Listing appears closed: ${result.reason}`,
          type: 'auto',
        });
        changed = true;

        if (settings?.notificationsEnabled !== false) {
          chrome.notifications.create(`closed-${job.id}-${Date.now()}`, {
            type: 'basic',
            iconUrl: 'icons/icon128.png',
            title: 'Job Listing Update',
            message: `"${job.title || 'A job'}" at ${job.company || 'unknown company'} appears to be closed.`,
          });
        }
      } else if (!result.isClosed) {
        job.autoStatus = 'active';
        const lastEvent = job.timeline[job.timeline.length - 1];
        const isRecentCheck =
          lastEvent?.type === 'check' &&
          Date.now() - new Date(lastEvent.date).getTime() < 24 * 60 * 60 * 1000;
        if (!isRecentCheck) {
          job.timeline.push({
            date: now,
            event: 'Listing verified active',
            type: 'check',
          });
        }
      }
    } catch {
      job.lastChecked = new Date().toISOString();
    }
  }

  await chrome.storage.local.set({ jobs });
}

async function checkJobUrl(url) {
  try {
    const response = await fetch(url, {
      method: 'GET',
      redirect: 'follow',
      signal: AbortSignal.timeout(15000),
    });

    if (response.status === 404 || response.status === 410) {
      return { isClosed: true, reason: `HTTP ${response.status}` };
    }
    if (!response.ok) {
      return { isClosed: false, reason: 'unknown' };
    }

    const text = await response.text();
    const lower = text.toLowerCase();
    for (const signal of CLOSED_SIGNALS) {
      if (lower.includes(signal)) {
        return { isClosed: true, reason: signal };
      }
    }
    return { isClosed: false };
  } catch (err) {
    return { isClosed: false, reason: err.message };
  }
}

/* ── Reminders ────────────────────────────────────────── */

async function handleReminder(jobId) {
  const { jobs = [], settings } = await chrome.storage.local.get([
    'jobs',
    'settings',
  ]);
  const job = jobs.find((j) => j.id === jobId);
  if (!job) return;

  if (settings?.notificationsEnabled !== false) {
    chrome.notifications.create(`reminder-${job.id}-${Date.now()}`, {
      type: 'basic',
      iconUrl: 'icons/icon128.png',
      title: 'JobVault Reminder',
      message: `Follow up on "${job.title || 'a job'}" at ${job.company || 'unknown company'}`,
    });
  }

  if (!job.timeline) job.timeline = [];
  job.timeline.push({
    date: new Date().toISOString(),
    event: 'Reminder triggered',
    type: 'reminder',
  });
  job.reminderDate = null;
  await chrome.storage.local.set({ jobs });
}

/* ── Message Handler ──────────────────────────────────── */

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.action === 'setReminder') {
    const when = new Date(message.date).getTime();
    chrome.alarms.create(`${REMINDER_PREFIX}${message.jobId}`, { when });
    sendResponse({ success: true });
  }

  if (message.action === 'clearReminder') {
    chrome.alarms.clear(`${REMINDER_PREFIX}${message.jobId}`);
    sendResponse({ success: true });
  }

  if (message.action === 'checkNow') {
    checkAllJobs().then(() => sendResponse({ success: true }));
    return true;
  }

  if (message.action === 'getSettings') {
    chrome.storage.local.get('settings', ({ settings }) => {
      sendResponse({ settings });
    });
    return true;
  }

  if (message.action === 'saveSettings') {
    chrome.storage.local.set({ settings: message.settings }).then(() => {
      setupAlarm();
      sendResponse({ success: true });
    });
    return true;
  }

  if (message.action === 'backupToSync') {
    backupToSync()
      .then(() => sendResponse({ success: true }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (message.action === 'restoreFromSync') {
    restoreFromSync()
      .then((count) => sendResponse({ success: true, count }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }
});

/* ── Cloud Backup / Restore ───────────────────────────── */

async function backupToSync() {
  const { jobs = [] } = await chrome.storage.local.get('jobs');
  const slim = jobs.map((j) => ({
    id: j.id,
    title: j.title,
    company: j.company,
    location: j.location,
    url: j.url,
    status: j.status,
    tags: j.tags,
    salary: j.salary,
    dateSaved: j.dateSaved,
  }));
  const chunks = chunkArray(slim, 20);
  const data = { _chunks: chunks.length };
  chunks.forEach((chunk, i) => {
    data[`jobs_${i}`] = chunk;
  });
  await chrome.storage.sync.set(data);
}

async function restoreFromSync() {
  const syncData = await chrome.storage.sync.get(null);
  if (!syncData._chunks) throw new Error('No backup found');
  const allSynced = [];
  for (let i = 0; i < syncData._chunks; i++) {
    if (syncData[`jobs_${i}`]) allSynced.push(...syncData[`jobs_${i}`]);
  }
  const { jobs = [] } = await chrome.storage.local.get('jobs');
  let added = 0;
  for (const synced of allSynced) {
    const exists = jobs.some((j) => j.id === synced.id || (j.url && j.url === synced.url));
    if (!exists) {
      jobs.push({
        ...synced,
        description: '',
        notes: '',
        timeline: [{ date: new Date().toISOString(), event: 'Restored from cloud backup', type: 'manual' }],
        autoStatus: 'active',
        lastChecked: null,
        lastUpdated: new Date().toISOString(),
      });
      added++;
    }
  }
  await chrome.storage.local.set({ jobs });
  return added;
}

function chunkArray(arr, size) {
  const chunks = [];
  for (let i = 0; i < arr.length; i += size) {
    chunks.push(arr.slice(i, i + size));
  }
  return chunks;
}

/* ── Notification Click ───────────────────────────────── */

chrome.notifications.onClicked.addListener((notificationId) => {
  chrome.tabs.create({ url: chrome.runtime.getURL('jobs.html') });
  chrome.notifications.clear(notificationId);
});
