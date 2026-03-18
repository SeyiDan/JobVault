(() => {
  if (window.__jobVaultInjected) return;
  window.__jobVaultInjected = true;

  /* ── Helpers ─────────────────────────────────────────── */

  function getText(selectors) {
    for (const sel of selectors) {
      try {
        const el = document.querySelector(sel);
        if (el) {
          const text = el.innerText?.trim();
          if (text) return text;
        }
      } catch { /* invalid selector — skip */ }
    }
    return '';
  }

  function getMetaContent(property) {
    const meta =
      document.querySelector(`meta[property="${property}"]`) ||
      document.querySelector(`meta[name="${property}"]`);
    return meta?.getAttribute('content')?.trim() || '';
  }

  function getHref(selectors) {
    for (const sel of selectors) {
      try {
        const el = document.querySelector(sel);
        if (el?.href) return el.href;
      } catch {}
    }
    return '';
  }

  /* ── Salary Detection ────────────────────────────────── */

  function detectSalary() {
    const ldScripts = document.querySelectorAll('script[type="application/ld+json"]');
    for (const script of ldScripts) {
      try {
        const data = JSON.parse(script.textContent);
        const posting = data['@type'] === 'JobPosting' ? data : null;
        if (posting?.baseSalary) {
          const s = posting.baseSalary;
          if (s.value) {
            const v = s.value;
            const cur = s.currency || 'USD';
            if (v.minValue && v.maxValue)
              return `${cur} ${Number(v.minValue).toLocaleString()} – ${Number(v.maxValue).toLocaleString()} / ${v.unitText || 'year'}`;
            if (v.value)
              return `${cur} ${Number(v.value).toLocaleString()} / ${v.unitText || 'year'}`;
          }
        }
        if (posting?.estimatedSalary) {
          const s = Array.isArray(posting.estimatedSalary)
            ? posting.estimatedSalary[0]
            : posting.estimatedSalary;
          if (s?.value) {
            const v = s.value;
            const cur = s.currency || 'USD';
            if (v.minValue && v.maxValue)
              return `${cur} ${Number(v.minValue).toLocaleString()} – ${Number(v.maxValue).toLocaleString()}`;
          }
        }
      } catch {}
    }

    const fromEl = getText([
      '[class*="salary" i]',
      '[class*="compensation" i]',
      '[class*="pay-range" i]',
      '[data-testid*="salary" i]',
    ]);
    if (fromEl) return fromEl;

    const salaryPatterns = [
      /\$[\d,]+(?:\.\d{2})?\s*[–\-]\s*\$[\d,]+(?:\.\d{2})?(?:\s*(?:per|\/|a)\s*(?:year|yr|annum|month|hour|hr))?/i,
      /(?:salary|compensation|pay)[:\s]*\$[\d,]+(?:\.\d{2})?(?:\s*[–\-]\s*\$[\d,]+(?:\.\d{2})?)?/i,
      /\$[\d,]+k?\s*[–\-]\s*\$[\d,]+k?/i,
    ];
    const bodyText = document.body.innerText.substring(0, 10000);
    for (const pattern of salaryPatterns) {
      const match = bodyText.match(pattern);
      if (match) return match[0];
    }
    return '';
  }

  /* ── Apply URL Detection ─────────────────────────────── */

  function detectApplyUrl() {
    const selectors = [
      'a[href*="apply"]',
      'a[class*="apply" i]',
      '[data-testid*="apply" i] a',
      '.jobs-apply-button',
      '.apply-button a',
    ];
    for (const sel of selectors) {
      try {
        const el = document.querySelector(sel);
        if (el?.href && el.href !== window.location.href) return el.href;
      } catch {}
    }
    return '';
  }

  /* ── Site-Specific Extractors ────────────────────────── */

  const extractors = [
    {
      name: 'linkedin',
      test: (url) => /linkedin\.com\/jobs/.test(url),
      extract: () => ({
        title: getText([
          'h1.t-24',
          '.top-card-layout__title',
          '.jobs-unified-top-card__job-title',
          'h1.topcard__title',
          'h1',
        ]),
        company: getText([
          '.jobs-unified-top-card__company-name a',
          '.jobs-unified-top-card__company-name',
          '.topcard__org-name-link',
          'a.topcard__org-name-link',
          '.top-card-layout__card .topcard__flavor:first-child a',
        ]),
        location: getText([
          '.jobs-unified-top-card__bullet',
          '.topcard__flavor.topcard__flavor--bullet',
          '.top-card-layout__card .topcard__flavor--bullet',
        ]),
        description: getText([
          '.show-more-less-html__markup',
          '.jobs-description__content .jobs-box__html-content',
          '#job-details',
          '.description__text .show-more-less-html__markup',
        ]),
        salary:
          getText([
            '.jobs-unified-top-card__job-insight .jobs-unified-top-card__job-insight-view-model-secondary',
            '.salary-main-rail__data-val',
          ]) || detectSalary(),
        applyUrl:
          getHref(['.jobs-apply-button--top-card a', '.apply-button a']) ||
          detectApplyUrl(),
      }),
    },
    {
      name: 'indeed',
      test: (url) => /indeed\.com/.test(url),
      extract: () => ({
        title: getText([
          'h1.jobsearch-JobInfoHeader-title',
          '[data-testid="jobsearch-JobInfoHeader-title"]',
          'h1.icl-u-xs-mb--xs',
          'h1',
        ]),
        company: getText([
          '[data-company-name]',
          '[data-testid="inlineHeader-companyName"] a',
          '[data-testid="inlineHeader-companyName"]',
          '.jobsearch-InlineCompanyRating-companyHeader a',
          '.jobsearch-InlineCompanyRating a',
        ]),
        location: getText([
          '[data-testid="job-location"]',
          '[data-testid="inlineHeader-companyLocation"]',
          '.jobsearch-JobInfoHeader-subtitle > div:last-child',
          '.css-6z8o9s',
        ]),
        description: getText([
          '#jobDescriptionText',
          '.jobsearch-JobComponent-description',
          '#jobDescription',
        ]),
        salary:
          getText([
            '[data-testid="attribute_snippet_testid"]',
            '#salaryInfoAndJobType',
            '.salary-snippet-container',
          ]) || detectSalary(),
        applyUrl:
          getHref([
            '.jobsearch-IndeedApplyButton a',
            '[data-testid="indeedApply"] a',
          ]) || detectApplyUrl(),
      }),
    },
    {
      name: 'greenhouse',
      test: (url) => /greenhouse\.io|boards\.greenhouse/.test(url),
      extract: () => ({
        title: getText(['.app-title', 'h1.heading', '.job__title', 'h1']),
        company:
          getText(['.company-name', '.job__company']) ||
          getMetaContent('og:site_name'),
        location: getText(['.location', '.job__location', '.body--metadata']),
        description: getText([
          '#content .content-intro + div',
          '#content',
          '.job__description',
        ]),
        salary: detectSalary(),
        applyUrl:
          getHref(['a[href*="application"]', '.btn--apply']) ||
          detectApplyUrl(),
      }),
    },
    {
      name: 'lever',
      test: (url) => /lever\.co/.test(url),
      extract: () => ({
        title: getText(['.posting-headline h2', '.posting-headline', 'h1']),
        company:
          getText([
            '.posting-headline .sort-by-time',
            '.posting-categories .sort-by-time',
          ]) || getMetaContent('og:site_name'),
        location: getText([
          '.posting-categories .sort-by-time .location',
          '.location',
          '.posting-categories .workplaceTypes',
        ]),
        description: getText([
          '.posting-page [data-qa="job-description"]',
          '.section-wrapper.page-full-width',
          '.posting-page .content',
        ]),
        salary: detectSalary(),
        applyUrl:
          getHref([
            'a.postings-btn',
            '.template-btn-submit a',
            '[data-qa="btn-apply"]',
          ]) || detectApplyUrl(),
      }),
    },
    {
      name: 'workday',
      test: (url) => /myworkdayjobs\.com|workday\.com\/.*\/job/.test(url),
      extract: () => ({
        title: getText([
          '[data-automation-id="jobPostingHeader"] h2',
          'h2[data-automation-id="jobPostingTitle"]',
          'h1',
          'h2',
        ]),
        company:
          getMetaContent('og:site_name') ||
          getText(['.css-company-name']),
        location: getText([
          '[data-automation-id="locations"]',
          '[data-automation-id="jobPostingLocation"]',
        ]),
        description: getText([
          '[data-automation-id="jobPostingDescription"]',
          '#mainContent',
        ]),
        salary: detectSalary(),
        applyUrl:
          getHref([
            'a[data-automation-id="applyButton"]',
            '[data-automation-id="applyBtn"] a',
          ]) || detectApplyUrl(),
      }),
    },
    {
      name: 'glassdoor',
      test: (url) => /glassdoor\.com/.test(url),
      extract: () => ({
        title: getText([
          '[data-test="jobTitle"]',
          '.css-1vg6q84',
          'h1',
        ]),
        company: getText([
          '[data-test="employerName"]',
          '.css-87uc0g',
        ]),
        location: getText([
          '[data-test="location"]',
          '.css-56kyx5',
        ]),
        description: getText([
          '[data-test="jobDescriptionContent"]',
          '.jobDescriptionContent',
          '#JobDescriptionContainer',
        ]),
        salary:
          getText([
            '[data-test="detailSalary"]',
            '.salary-estimate',
          ]) || detectSalary(),
        applyUrl:
          getHref(['[data-test="applyButton"] a', '.applyButton a']) ||
          detectApplyUrl(),
      }),
    },
    {
      name: 'wellfound',
      test: (url) => /wellfound\.com|angel\.co/.test(url),
      extract: () => ({
        title: getText([
          'h1[class*="title"]',
          '.listing-title',
          'h1',
        ]),
        company: getText([
          'a[class*="company"]',
          '.company-summary h2',
        ]),
        location: getText([
          '[class*="location"]',
          '.tags .tag',
        ]),
        description: getText([
          '.description',
          '[class*="description"]',
          '.job-description',
        ]),
        salary:
          getText([
            '[class*="salary"]',
            '[class*="compensation"]',
          ]) || detectSalary(),
        applyUrl: detectApplyUrl(),
      }),
    },
  ];

  /* ── Generic Fallback Extractor ──────────────────────── */

  function genericExtract() {
    const ogTitle = getMetaContent('og:title');
    const title =
      ogTitle ||
      getText(['h1', '[class*="title" i]', '[class*="jobTitle" i]']) ||
      document.title;

    const company =
      getMetaContent('og:site_name') ||
      getText([
        '[class*="company" i]',
        '[class*="employer" i]',
        '[class*="org-name" i]',
      ]);

    const location = getText([
      '[class*="location" i]',
      '[class*="jobLocation" i]',
    ]);

    const description =
      getText([
        '[class*="description" i]',
        '[class*="job-detail" i]',
        '[class*="jobDetail" i]',
        'article',
        'main',
        '#content',
        '.content',
      ]) || document.body.innerText.substring(0, 5000);

    const salary = detectSalary();
    const applyUrl = detectApplyUrl();

    return { title, company, location, description, salary, applyUrl };
  }

  /* ── Main Extraction Entry Point ─────────────────────── */

  function extractJobData() {
    const url = window.location.href;

    for (const extractor of extractors) {
      if (extractor.test(url)) {
        const data = extractor.extract();
        if (data.title || data.description) {
          return { ...data, url };
        }
      }
    }

    const fallback = genericExtract();
    return { ...fallback, url };
  }

  /* ── Message Listener ────────────────────────────────── */

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message.action === 'extractJob') {
      try {
        const data = extractJobData();
        sendResponse({ success: true, data });
      } catch (err) {
        sendResponse({ success: false, error: err.message });
      }
    }
    return true;
  });
})();
