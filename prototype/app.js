/*
 * WelFamily public page.
 * All catalog text reaches the page through textContent, so it can't inject markup.
 * The page moves through one state at a time: loading -> ready, or loading -> error -> loading.
 */
(() => {
  'use strict';

  const PAGE_SIZE = 30;
  const FETCH_TIMEOUT_MS = 10000;
  const STALE_AFTER_DAYS = 7;
  const FALLBACK_URL = 'https://www.bokjiro.go.kr';
  const FALLBACK_PHONE = '129';
  const REGION_KEY = 'welfamily_user_profile_v1';
  const TEXT_SIZE_KEY = 'welfamily_large_text';

  // A small pilot list. P4 replaces this with the official region table.
  const REGIONS = {
    seoul: { name: '서울특별시', sigungu: { gwanak: '관악구', gangnam: '강남구', mapo: '마포구' } },
    gyeonggi: { name: '경기도', sigungu: { seongnam: '성남시', suwon: '수원시', yongin: '용인시' } },
    busan: { name: '부산광역시', sigungu: { haeundae: '해운대구', busanjin: '부산진구' } },
  };

  const CATEGORY_ORDER = ['CASH', 'VOUCHER', 'DISCOUNT', 'CARE', 'HOUSING', 'MEDICAL', 'JOB', 'EDUCATION'];

  const state = {
    status: 'loading',
    policies: [],
    sido: '',
    sigungu: '',
    query: '',
    category: 'ALL',
    origin: 'ALL',
    visible: PAGE_SIZE,
  };

  // Document checks last for this visit only. They are never stored.
  const checkedDocs = new Map();
  let lastTrigger = null;

  const byId = (id) => document.getElementById(id);
  const el = {
    sido: byId('region-sido'),
    sigungu: byId('region-sigungu'),
    remember: byId('region-remember'),
    textSize: byId('text-size-toggle'),
    stamp: byId('data-stamp'),
    search: byId('search-input'),
    clear: byId('search-clear'),
    filters: byId('filters'),
    filterCount: byId('filter-count'),
    categories: byId('category-filters'),
    origins: byId('origin-filters'),
    title: byId('results-title'),
    summary: byId('results-summary'),
    list: byId('policy-list'),
    skeleton: byId('policy-skeleton'),
    legend: byId('results-legend'),
    empty: byId('results-empty'),
    emptyTitle: byId('empty-title'),
    emptyText: byId('empty-text'),
    emptyAction: byId('empty-action'),
    error: byId('results-error'),
    retry: byId('retry-button'),
    moreWrap: byId('show-more'),
    more: byId('show-more-button'),
    cardTemplate: byId('policy-card-template'),
    dialog: byId('policy-dialog'),
    dialogClose: byId('dialog-close'),
    dialogChips: byId('dialog-chips'),
    dialogOrg: byId('dialog-org'),
    dialogTitle: byId('dialog-title'),
    dialogAmount: byId('dialog-amount'),
    factWho: byId('fact-who'),
    factWhat: byId('fact-what'),
    factHow: byId('fact-how'),
    docSection: byId('doc-section'),
    docList: byId('doc-list'),
    docProgress: byId('doc-progress'),
    phone: byId('dialog-phone'),
    phoneText: byId('dialog-phone-text'),
    link: byId('dialog-link'),
  };

  // ------------------------------------------------------------------ storage
  const storage = {
    get(key) {
      try {
        return localStorage.getItem(key);
      } catch (error) {
        return null;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, value);
      } catch (error) {
        console.warn('Could not save to this browser:', error);
      }
    },
    remove(key) {
      try {
        localStorage.removeItem(key);
      } catch (error) {
        console.warn('Could not delete from this browser:', error);
      }
    },
  };

  // ------------------------------------------------------------------ data
  async function fetchFirst(paths) {
    for (const path of paths) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
      try {
        const response = await fetch(path, { signal: controller.signal });
        if (response.ok) return await response.json();
      } catch (error) {
        console.warn(`Could not load ${path}:`, error);
      } finally {
        clearTimeout(timer);
      }
    }
    throw new Error('No data source responded');
  }

  const compact = (text) => String(text || '').toLowerCase().replace(/\s+/g, '');

  function toPolicy(item) {
    const summary = item.summary_3lines || [];
    const docs = (item.required_documents || []).map((doc) => ({
      name: doc.name,
      issuer: doc.issuer,
    }));
    return {
      id: item.id,
      title: item.title,
      origin: item.origin,
      region: item.region_code,
      regionName: item.region_name,
      org: item.managing_org,
      category: item.category,
      categoryName: item.category_name,
      amountText: item.amount_text,
      summary,
      docs,
      phone: item.contact_phone,
      url: item.application_url,
      searchText: compact([item.title, item.managing_org, ...summary, ...docs.map((doc) => doc.name)].join(' ')),
    };
  }

  async function loadData() {
    state.status = 'loading';
    render();
    try {
      const catalog = await fetchFirst(['data/welfare_catalog.json', '../data/welfare_catalog.json']);
      if (!Array.isArray(catalog.policies) || catalog.policies.length === 0) {
        throw new Error('The catalog is empty');
      }
      state.policies = catalog.policies.map(toPolicy);
      state.status = 'ready';
    } catch (error) {
      console.warn('Could not load the catalog:', error);
      state.status = 'error';
    }
    render();
    loadDataStamp();
  }

  async function loadDataStamp() {
    try {
      const meta = await fetchFirst(['data/latest_sync.json', '../data/latest_sync.json']);
      const date = new Date(meta.last_sync_at);
      if (Number.isNaN(date.getTime())) return;
      const days = Math.max(0, Math.floor((Date.now() - date.getTime()) / 86400000));
      const label = date.toLocaleDateString('ko-KR', { timeZone: 'Asia/Seoul' });
      const age = days === 0 ? '오늘' : `${days}일 전`;
      el.stamp.textContent = `데이터 기준일: ${label} (${age})`;
      el.stamp.classList.toggle('is-stale', days > STALE_AFTER_DAYS);
    } catch (error) {
      console.warn('Could not load the data date:', error);
    }
  }

  // ------------------------------------------------------------------ filters
  function inRegion(policy) {
    if (policy.region === 'ALL') return true;
    if (!state.sido) return false;
    if (policy.region === state.sido) return true;
    return Boolean(state.sigungu) && policy.region === `${state.sido}_${state.sigungu}`;
  }

  const inOrigin = (policy) => state.origin === 'ALL' || policy.origin === state.origin;
  const inCategory = (policy) => state.category === 'ALL' || policy.category === state.category;

  function inQuery(policy) {
    const query = compact(state.query);
    return !query || policy.searchText.includes(query);
  }

  // Local benefits come first: they are the hardest ones to find elsewhere.
  function localFirst(a, b) {
    return (a.origin === 'LOCAL' ? 0 : 1) - (b.origin === 'LOCAL' ? 0 : 1);
  }

  function regionLabel() {
    if (!state.sido) return '';
    const sido = REGIONS[state.sido];
    return state.sigungu ? `${sido.name} ${sido.sigungu[state.sigungu]}` : sido.name;
  }

  // ------------------------------------------------------------------ rendering
  function setChip(chip, policy) {
    const isLocal = policy.origin === 'LOCAL';
    chip.classList.add(isLocal ? 'chip--local' : 'chip--national');
    chip.querySelector('[data-slot="origin-text"]').textContent = isLocal ? policy.regionName : '전국 공통';
    chip.querySelector('.icon').toggleAttribute('hidden', !isLocal);
  }

  function buildCard(policy) {
    const node = el.cardTemplate.content.cloneNode(true);
    const slot = (name) => node.querySelector(`[data-slot="${name}"]`);
    setChip(slot('origin'), policy);
    slot('category').textContent = policy.categoryName;
    slot('title').textContent = policy.title;
    slot('title').dataset.policyId = policy.id;
    slot('org').textContent = policy.org;
    slot('summary').textContent = policy.summary[0] || '';
    slot('amount').textContent = policy.amountText;
    return node;
  }

  function buildFilterButton({ label, count, active, disabled, value }) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'filter-chip';
    button.dataset.value = value;
    button.setAttribute('aria-pressed', String(active));
    button.disabled = disabled;
    const text = document.createElement('span');
    text.textContent = label;
    const number = document.createElement('span');
    number.className = 'filter-chip__count';
    number.textContent = count;
    button.append(text, number);
    return button;
  }

  // Rebuilding a filter must not lose keyboard focus, so focus is put back afterward.
  function replaceFilters(container, buttons) {
    const focused = document.activeElement;
    const focusedValue = container.contains(focused) ? focused.dataset.value : null;
    container.replaceChildren(...buttons);
    if (focusedValue) {
      const next = buttons.find((button) => button.dataset.value === focusedValue && !button.disabled);
      (next || el.search).focus();
    }
  }

  function renderFilters() {
    const scoped = state.policies.filter((policy) => inRegion(policy) && inQuery(policy));

    const active = Number(state.category !== 'ALL') + Number(state.origin !== 'ALL');
    el.filterCount.textContent = active ? ` (${active}개 적용 중)` : '';

    const forCategories = scoped.filter(inOrigin);
    const names = new Map(state.policies.map((policy) => [policy.category, policy.categoryName]));
    const categories = CATEGORY_ORDER.filter((code) => names.has(code));
    replaceFilters(el.categories, [
      buildFilterButton({
        label: '전체', value: 'ALL', count: forCategories.length, active: state.category === 'ALL', disabled: false,
      }),
      ...categories.map((code) => {
        const count = forCategories.filter((policy) => policy.category === code).length;
        return buildFilterButton({
          label: names.get(code), value: code, count, active: state.category === code, disabled: count === 0 && state.category !== code,
        });
      }),
    ]);

    const forOrigins = scoped.filter(inCategory);
    const countOf = (origin) => forOrigins.filter((policy) => policy.origin === origin).length;
    replaceFilters(el.origins, [
      buildFilterButton({ label: '전체', value: 'ALL', count: forOrigins.length, active: state.origin === 'ALL', disabled: false }),
      buildFilterButton({ label: '우리 지역', value: 'LOCAL', count: countOf('LOCAL'), active: state.origin === 'LOCAL', disabled: false }),
      buildFilterButton({ label: '전국 공통', value: 'CENTRAL', count: countOf('CENTRAL'), active: state.origin === 'CENTRAL', disabled: false }),
    ]);
  }

  function renderEmpty() {
    const needsRegion = state.origin === 'LOCAL' && !state.sido;
    el.emptyTitle.textContent = needsRegion ? '먼저 사는 곳을 골라 주세요' : '조건에 맞는 복지를 찾지 못했어요';
    el.emptyText.textContent = needsRegion
      ? '지역을 고르면 그 지역의 복지를 보여 드려요.'
      : '검색어를 바꾸거나 조건을 지워 보세요. 복지로나 129에서도 찾아볼 수 있어요.';
    el.emptyAction.textContent = needsRegion ? '지역 고르기' : '조건 지우기';
    el.emptyAction.dataset.action = needsRegion ? 'pick-region' : 'reset';
  }

  function render() {
    const loading = state.status === 'loading';
    const failed = state.status === 'error';
    const ready = state.status === 'ready';

    el.skeleton.hidden = !loading;
    el.error.hidden = !failed;
    el.list.hidden = !ready;
    el.legend.hidden = !ready;
    el.list.closest('section').setAttribute('aria-busy', String(loading));

    el.title.textContent = regionLabel() ? `${regionLabel()} 복지` : '전국 공통 복지';

    if (!ready) {
      el.empty.hidden = true;
      el.moreWrap.hidden = true;
      el.summary.textContent = loading ? '복지 정보를 불러오고 있어요.' : '복지 정보를 불러오지 못했어요.';
      return;
    }

    renderFilters();

    const matches = state.policies
      .filter((policy) => inRegion(policy) && inOrigin(policy) && inCategory(policy) && inQuery(policy))
      .sort(localFirst);
    const localCount = matches.filter((policy) => policy.origin === 'LOCAL').length;

    if (matches.length === 0) {
      el.summary.textContent = '찾은 복지가 없어요.';
    } else if (state.sido) {
      el.summary.textContent = `총 ${matches.length}건 (우리 지역 ${localCount}건, 전국 공통 ${matches.length - localCount}건)`;
    } else {
      el.summary.textContent = `총 ${matches.length}건. 사는 곳을 고르면 지역 복지도 함께 보여 드려요.`;
    }
    el.legend.hidden = matches.length === 0;

    const shown = matches.slice(0, state.visible);
    el.list.replaceChildren(...shown.map(buildCard));

    el.empty.hidden = matches.length > 0;
    if (matches.length === 0) renderEmpty();

    const remaining = matches.length - shown.length;
    el.moreWrap.hidden = remaining <= 0;
    el.more.textContent = `${Math.min(remaining, PAGE_SIZE)}건 더 보기 (남은 ${remaining}건)`;
  }

  function refresh() {
    state.visible = PAGE_SIZE;
    render();
  }

  // ------------------------------------------------------------------ region
  function fillSigungu() {
    const sido = REGIONS[state.sido];
    const options = [new Option(sido ? '시/군/구 전체' : '시/군/구 선택', '')];
    if (sido) {
      Object.entries(sido.sigungu).forEach(([code, name]) => options.push(new Option(name, code)));
    }
    el.sigungu.replaceChildren(...options);
    el.sigungu.disabled = !sido;
  }

  function saveRegion() {
    if (el.remember.checked && state.sido) {
      storage.set(REGION_KEY, JSON.stringify({ sido: state.sido, sigungu: state.sigungu }));
    } else {
      storage.remove(REGION_KEY);
    }
  }

  function restoreRegion() {
    try {
      const saved = JSON.parse(storage.get(REGION_KEY));
      if (saved && REGIONS[saved.sido]) {
        state.sido = saved.sido;
        state.sigungu = REGIONS[saved.sido].sigungu[saved.sigungu] ? saved.sigungu : '';
        el.remember.checked = true;
      }
    } catch (error) {
      storage.remove(REGION_KEY);
    }
    el.sido.value = state.sido;
    fillSigungu();
    el.sigungu.value = state.sigungu;
  }

  // ------------------------------------------------------------------ dialog
  function renderDocProgress(policy) {
    const total = policy.docs.length;
    const done = (checkedDocs.get(policy.id) || new Set()).size;
    const finished = total > 0 && done === total;
    el.docProgress.textContent = finished
      ? '서류를 모두 챙겼어요. 이제 공식 사이트에서 신청 방법을 확인하세요.'
      : `${total}개 중 ${done}개 챙겼어요.`;
    el.docProgress.classList.toggle('is-done', finished);
  }

  function buildDocItem(policy, doc, index) {
    const checked = checkedDocs.get(policy.id) || new Set();
    const label = document.createElement('label');
    label.className = 'doc-item';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = checked.has(index);
    input.addEventListener('change', () => {
      const current = checkedDocs.get(policy.id) || new Set();
      if (input.checked) current.add(index);
      else current.delete(index);
      checkedDocs.set(policy.id, current);
      renderDocProgress(policy);
    });
    const text = document.createElement('span');
    const name = document.createElement('span');
    name.className = 'doc-item__name';
    name.textContent = doc.name;
    text.append(name);
    if (doc.issuer) {
      const issuer = document.createElement('span');
      issuer.className = 'doc-item__issuer';
      issuer.textContent = doc.issuer;
      text.append(issuer);
    }
    label.append(input, text);
    return label;
  }

  function openDetail(policy, trigger) {
    lastTrigger = trigger;

    const originChip = el.dialogChips.querySelector('[data-slot="origin"]');
    originChip.classList.remove('chip--local', 'chip--national');
    setChip(originChip, policy);
    el.dialogChips.querySelector('[data-slot="category"]').textContent = policy.categoryName;

    el.dialogOrg.textContent = policy.org;
    el.dialogTitle.textContent = policy.title;
    el.dialogAmount.textContent = policy.amountText;
    el.factWho.textContent = policy.summary[0] || '공식 사이트에서 확인하세요.';
    el.factWhat.textContent = policy.summary[1] || '공식 사이트에서 확인하세요.';
    el.factHow.textContent = policy.summary[2] || '공식 사이트에서 확인하세요.';

    el.docSection.hidden = policy.docs.length === 0;
    el.docList.replaceChildren(...policy.docs.map((doc, index) => buildDocItem(policy, doc, index)));
    renderDocProgress(policy);

    const phone = policy.phone || FALLBACK_PHONE;
    el.phoneText.textContent = phone;
    el.phone.href = `tel:${phone.replace(/[^0-9+]/g, '')}`;

    // Only http and https links are allowed through.
    el.link.href = /^https?:\/\//.test(policy.url || '') ? policy.url : FALLBACK_URL;

    if (typeof el.dialog.showModal === 'function') el.dialog.showModal();
    else el.dialog.setAttribute('open', '');
  }

  function closeDetail() {
    if (typeof el.dialog.close === 'function') el.dialog.close();
    else el.dialog.removeAttribute('open');
  }

  // ------------------------------------------------------------------ text size
  function setLargeText(on) {
    document.documentElement.classList.toggle('large-text', on);
    el.textSize.setAttribute('aria-pressed', String(on));
  }

  // ------------------------------------------------------------------ events
  function resetFilters() {
    state.query = '';
    state.category = 'ALL';
    state.origin = 'ALL';
    el.search.value = '';
    el.clear.hidden = true;
    refresh();
    el.search.focus();
  }

  function clearSearch() {
    state.query = '';
    el.search.value = '';
    el.clear.hidden = true;
    refresh();
    el.search.focus();
  }

  el.sido.addEventListener('change', () => {
    state.sido = el.sido.value;
    state.sigungu = '';
    fillSigungu();
    saveRegion();
    refresh();
  });

  el.sigungu.addEventListener('change', () => {
    state.sigungu = el.sigungu.value;
    saveRegion();
    refresh();
  });

  el.remember.addEventListener('change', saveRegion);

  el.textSize.addEventListener('click', () => {
    const on = !document.documentElement.classList.contains('large-text');
    setLargeText(on);
    if (on) storage.set(TEXT_SIZE_KEY, '1');
    else storage.remove(TEXT_SIZE_KEY);
  });

  el.search.addEventListener('input', () => {
    state.query = el.search.value;
    el.clear.hidden = !state.query;
    refresh();
  });

  el.search.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && state.query) clearSearch();
  });

  el.clear.addEventListener('click', clearSearch);

  el.categories.addEventListener('click', (event) => {
    const button = event.target.closest('.filter-chip');
    if (!button || button.disabled) return;
    state.category = button.dataset.value;
    refresh();
  });

  el.origins.addEventListener('click', (event) => {
    const button = event.target.closest('.filter-chip');
    if (!button) return;
    state.origin = button.dataset.value;
    refresh();
  });

  el.list.addEventListener('click', (event) => {
    const button = event.target.closest('.card__open');
    if (!button) return;
    const policy = state.policies.find((item) => item.id === button.dataset.policyId);
    if (policy) openDetail(policy, button);
  });

  el.more.addEventListener('click', () => {
    const firstNew = state.visible;
    state.visible += PAGE_SIZE;
    render();
    const next = el.list.querySelectorAll('.card__open')[firstNew];
    if (next) next.focus();
  });

  el.emptyAction.addEventListener('click', () => {
    if (el.emptyAction.dataset.action === 'pick-region') el.sido.focus();
    else resetFilters();
  });

  el.retry.addEventListener('click', async () => {
    await loadData();
    if (state.status === 'ready') el.title.focus();
    else el.retry.focus();
  });

  el.dialogClose.addEventListener('click', closeDetail);

  // A click on the backdrop lands on the dialog element itself.
  el.dialog.addEventListener('click', (event) => {
    if (event.target === el.dialog) closeDetail();
  });

  el.dialog.addEventListener('close', () => {
    if (lastTrigger && lastTrigger.isConnected) lastTrigger.focus();
  });

  // Wide screens have room, so filters stay open there and the summary is hidden.
  const wideScreen = window.matchMedia('(min-width: 48rem)');
  const openFiltersOnWideScreen = () => {
    if (wideScreen.matches) el.filters.open = true;
  };
  wideScreen.addEventListener('change', openFiltersOnWideScreen);

  // ------------------------------------------------------------------ start
  openFiltersOnWideScreen();
  setLargeText(storage.get(TEXT_SIZE_KEY) === '1');
  restoreRegion();
  loadData();
})();
