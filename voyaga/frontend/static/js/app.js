/* ═══════════════════════════════════════════
   VOYAGA — Main Application JS
═══════════════════════════════════════════ */

const BASE_URL = '';

// ── AUTH ──────────────────────────────────
function getToken() { return localStorage.getItem('voyaga_access'); }
function getUser() { return JSON.parse(localStorage.getItem('voyaga_user') || 'null'); }

function setAuth(data) {
  localStorage.setItem('voyaga_access', data.tokens.access);
  localStorage.setItem('voyaga_refresh', data.tokens.refresh);
  localStorage.setItem('voyaga_user', JSON.stringify(data.user));
  updateNavUI(data.user);
  fetchAndUpdateWallet();
}

function logout() {
  localStorage.removeItem('voyaga_access');
  localStorage.removeItem('voyaga_refresh');
  localStorage.removeItem('voyaga_user');
  updateNavUI(null);
  showToast('Signed out successfully', 'success');
  window.location.href = '/';
}

function updateNavUI(user) {
  const actions = document.getElementById('navActions');
  const navUser = document.getElementById('navUser');
  if (!actions || !navUser) return;
  if (user) {
    actions.classList.add('hidden');
    navUser.classList.remove('hidden');
    document.getElementById('userAvatar').textContent = (user.first_name?.[0] || user.email[0]).toUpperCase();
    document.getElementById('walletAmount').textContent = '$' + (parseFloat(user.wallet_balance) || 0).toFixed(2);
  } else {
    actions.classList.remove('hidden');
    navUser.classList.add('hidden');
  }
}

// ── API ───────────────────────────────────
// silent=true → no toast on error (for background GET requests like loading listings)
async function api(url, method = 'GET', body = null, silent = false) {
  const headers = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) headers['Authorization'] = 'Bearer ' + token;

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  try {
    const res = await fetch(BASE_URL + url, opts);

    if (res.status === 401) {
      const refreshed = await tryRefresh();
      if (refreshed) return api(url, method, body, silent);
      if (getToken()) logout();
      return null;
    }

    // Handle non-JSON or empty responses
    const text = await res.text();
    if (!text) return res.ok ? {} : null;

    let data;
    try { data = JSON.parse(text); }
    catch { if (!res.ok && !silent) showToast('Server error. Please try again.', 'error'); return null; }

    if (!res.ok) {
      if (!silent) showToast(extractError(data), 'error');
      return null;
    }
    return data;
  } catch (err) {
    // Only show network error for user-triggered actions (POST/PUT/DELETE), not background GETs
    if (!silent && method !== 'GET') {
      showToast('Cannot connect to server. Is Django running?', 'error');
    }
    return null;
  }
}

async function tryRefresh() {
  const refresh = localStorage.getItem('voyaga_refresh');
  if (!refresh) return false;
  try {
    const res = await fetch(BASE_URL + '/api/auth/token/refresh/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh })
    });
    if (!res.ok) return false;
    const data = await res.json();
    localStorage.setItem('voyaga_access', data.access);
    return true;
  } catch { return false; }
}

function extractError(data) {
  if (typeof data === 'string') return data;
  if (data.detail) return data.detail;
  if (data.non_field_errors) return data.non_field_errors[0];
  const keys = Object.keys(data);
  if (keys.length) {
    const val = data[keys[0]];
    return Array.isArray(val) ? `${keys[0]}: ${val[0]}` : String(val);
  }
  return 'An error occurred';
}

// ── MODALS ────────────────────────────────
function showModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('hidden');
}
function hideModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('hidden');
}
function switchModal(from, to) { hideModal(from); showModal(to); }

document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) e.target.classList.add('hidden');
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') document.querySelectorAll('.modal-overlay').forEach(m => m.classList.add('hidden'));
});

// ── AUTH FORMS ────────────────────────────
async function handleLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('loginBtn');
  const errEl = document.getElementById('loginError');
  btn.textContent = 'Signing in...'; btn.disabled = true;
  errEl.classList.add('hidden');

  const result = await api('/api/auth/login/', 'POST', {
    email: document.getElementById('loginEmail').value,
    password: document.getElementById('loginPassword').value
  });

  btn.textContent = 'Sign In'; btn.disabled = false;

  if (result) {
    setAuth(result);
    hideModal('loginModal');
    showToast(`Welcome back, ${result.user.first_name || result.user.username}! 👋`, 'success');
    document.getElementById('loginForm').reset();
    // Reload page data after login
    if (typeof loadRecommended === 'function') loadRecommended();
    if (typeof loadProperties === 'function') loadProperties();
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const btn = document.getElementById('registerBtn');
  const errEl = document.getElementById('registerError');
  const succEl = document.getElementById('registerSuccess');
  btn.textContent = 'Creating account...'; btn.disabled = true;
  errEl.classList.add('hidden'); succEl.classList.add('hidden');

  const result = await api('/api/auth/register/', 'POST', {
    email: document.getElementById('regEmail').value,
    username: document.getElementById('regUsername').value,
    first_name: document.getElementById('regFirst').value,
    last_name: document.getElementById('regLast').value,
    role: document.getElementById('regRole').value,
    password: document.getElementById('regPassword').value,
    password2: document.getElementById('regPassword2').value
  });

  btn.textContent = 'Create Account'; btn.disabled = false;

  if (result) {
    setAuth(result);
    succEl.textContent = '✓ Account created! Welcome to Voyaga.';
    succEl.classList.remove('hidden');
    setTimeout(() => {
      hideModal('registerModal');
      showToast('Welcome to Voyaga! 🎉', 'success');
      document.getElementById('registerForm').reset();
    }, 1500);
  }
}

// ── TOAST ─────────────────────────────────
let toastTimer;
function showToast(msg, type = '') {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.className = 'toast' + (type ? ' ' + type : '');
  toast.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add('hidden'), 3500);
}

// ── PROPERTY CARDS ────────────────────────
function propertyCard(p) {
  const img = p.primary_image_url
    ? `<img src="${p.primary_image_url}" alt="${p.title}" loading="lazy">`
    : `<div class="card-no-img">🏠</div>`;
  const stars = p.avg_rating ? `★ ${p.avg_rating}` : '✦ New';
  return `
    <div class="property-card" onclick="window.location.href='/property/${p.id}'">
      <div class="card-image">
        ${img}
        <div class="card-type-badge">${p.property_type}</div>
      </div>
      <div class="card-body">
        <div class="card-location">📍 ${p.city}, ${p.country}</div>
        <div class="card-title">${p.title}</div>
        <div class="card-specs">
          <span>👥 ${p.max_guests}</span>
          <span>🛏 ${p.bedrooms}bd</span>
          <span>🚿 ${p.bathrooms}ba</span>
        </div>
        <div class="card-footer">
          <div class="card-price">$${parseFloat(p.price_per_night).toFixed(0)}<span class="card-price-night">/night</span></div>
          <div class="card-rating">${stars}</div>
        </div>
      </div>
    </div>`;
}

// ── AI CHAT ───────────────────────────────
function toggleChat() {
  const panel = document.getElementById('chatPanel');
  panel.classList.toggle('hidden');
  if (!panel.classList.contains('hidden')) document.getElementById('chatInput').focus();
}

function quickChat(msg) {
  document.getElementById('chatInput').value = msg;
  sendChat();
}

async function sendChat() {
  const input = document.getElementById('chatInput');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';

  appendMsg(msg, 'user');

  if (!getToken()) {
    appendMsg("Please sign in to chat with Voya AI! Click **Sign in** in the top right. 👋", 'ai');
    return;
  }

  showThinking(true);
  const result = await api('/api/auth/chat/', 'POST', { message: msg });
  showThinking(false);
  if (result) appendMsg(result.reply, 'ai');
  else appendMsg("Sorry, I had trouble connecting. Please try again!", 'ai');
}

function appendMsg(text, role) {
  const container = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = `chat-msg ${role}`;
  div.innerHTML = `<div class="msg-bubble">${text}</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function showThinking(show) {
  document.getElementById('thinkingIndicator').classList.toggle('hidden', !show);
}

// ── NAVBAR SCROLL ─────────────────────────
window.addEventListener('scroll', () => {
  const nav = document.getElementById('navbar');
  if (nav) nav.classList.toggle('scrolled', window.scrollY > 50);
});

document.addEventListener('DOMContentLoaded', () => {
  const user = getUser();
  updateNavUI(user);
  if (user) fetchAndUpdateWallet();
});
function toggleDropdown() {
  const dd = document.getElementById('userDropdown');
  if (dd) dd.classList.toggle('open');
}

document.addEventListener('click', function(e) {
  const menu = document.getElementById('userMenuBtn');
  const dd = document.getElementById('userDropdown');
  if (dd && menu && !menu.contains(e.target)) {
    dd.classList.remove('open');
  }
});
async function refreshWallet() {
  const data = await api('/api/payments/wallet/');
  if (data) {
    const amount = '$' + parseFloat(data.balance).toFixed(2);
    const badge = document.getElementById('walletAmount');
    if (badge) badge.textContent = amount;
    const user = getUser();
    if (user) {
      user.wallet_balance = data.balance;
      localStorage.setItem('voyaga_user', JSON.stringify(user));
    }
  }
}
async function fetchAndUpdateWallet() {
  try {
    const data = await api('/api/payments/wallet/');
    if (data) {
      const formatted = '$' + parseFloat(data.balance).toFixed(2);
      const badge = document.getElementById('walletAmount');
      if (badge) badge.textContent = formatted;
      const user = getUser();
      if (user) {
        user.wallet_balance = data.balance;
        localStorage.setItem('voyaga_user', JSON.stringify(user));
      }
    }
  } catch (e) {}
}