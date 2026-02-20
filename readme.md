# 🌍 Voyaga — Travel Reimagined for the Digital Age

> A next-generation luxury travel booking platform powered by cryptocurrency, AI intelligence, and conscious travel tools.

![Django](https://img.shields.io/badge/Django-4.x-092E20?style=for-the-badge&logo=django)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python)
![JavaScript](https://img.shields.io/badge/JavaScript-Vanilla-F7DF1E?style=for-the-badge&logo=javascript)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

---

## ✦ What is Voyaga?

Voyaga is a full-stack Airbnb-style travel platform where users can browse, book, and list luxury properties — all paid with cryptocurrency. It combines a polished dark-themed UI with a Django REST backend, featuring AI-powered chat, real-time booking calendars, loyalty rewards, host analytics, and carbon footprint tracking.

**Built by Team Voyaga(DE)**

---

## 🚀 Feature Overview

### 🏡 Property Management
- Browse and search by city, country, type, price, and guests
- Full property detail with multi-image gallery and lightbox viewer
- Multi-photo upload with drag & drop (up to 10 photos, auto cover image)
- Hosts can list, delist, and re-activate properties anytime
- My Listings dashboard for full host property management

### ₿ Crypto Payments
- **7 cryptocurrencies:** Bitcoin, Ethereum, USDT, Solana, Litecoin, BNB, Dogecoin
- 4-step simulated payment flow with wallet address generation
- Real-time USD → crypto conversion rates
- Zero hidden fees for guests

### ⚡ Instant Host Payouts
- Hosts receive **97% of every booking immediately** on confirmation
- Cancellations automatically reverse the host payout
- Full transaction history in wallet

### 📅 Live Availability Calendar
- Visual calendar on every property showing exactly which dates are blocked
- Intelligent conflict detection — zero double-bookings possible
- Month navigation with past-date greyed out

### ❤️ Wishlist
- Heart any property to save it to a personal wishlist
- Toggle on/off instantly — persists per user account
- Dedicated `/wishlist` page

### 🏆 Loyalty Rewards

| Tier | Points | Discount |
|------|--------|----------|
| 🧭 Explorer | 0 pts | Standard |
| 🥈 Silver | 500 pts | 5% off |
| 🥇 Gold | 2,000 pts | 7% off |
| 💎 Platinum | 5,000 pts | 10% off |

- 1 loyalty point per $1 spent — shown in booking card and profile

### 📊 Host Analytics Dashboard
- 6-month earnings bar chart with booking count overlay (Chart.js)
- Per-property performance: bookings, earnings, rating, live/delisted status
- Monthly and all-time earnings totals

### 🤖 Voya AI Concierge
- Powered by **Anthropic Claude API** with live database access
- Reads real properties, reviews, and the user's loyalty tier in real time
- Typing animation, conversation history, quick-reply chips
- Smart fallback system when API key not configured

### 🌱 Carbon Footprint Tracker
- CO₂ (kg), energy (kWh), water (L) per night per property
- Based on property type with pool multiplier
- Low / Medium / High rating shown on every listing and booking summary

### 🔔 Smart Notifications
- Bell icon in navbar with unread count badge
- Hosts notified on new bookings (with payout) and cancellations (with reversal)
- Auto-polls every 60 seconds

### ⭐ Verified Reviews
- Star rating with animated picker (1–5)
- One review per user per property enforced
- Shown on property detail page with reviewer name and date

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend Framework | Django 4.x |
| API | Django REST Framework |
| Auth | Simple JWT |
| Database | SQLite (dev) |
| Images | Pillow |
| AI | Anthropic Claude API (claude-haiku) |
| Frontend | Vanilla JS + Django Templates |
| Charts | Chart.js (CDN) |
| Fonts | Google Fonts — Playfair Display + DM Sans |

---

## 📁 Project Structure

```
voyaga/
├── backend/
│   ├── apps/
│   │   ├── core/           # Users, Auth, Reviews, Chat, Notifications
│   │   ├── properties/     # Listings, Images, Search, Recommendations
│   │   ├── bookings/       # Bookings, Wishlist, Availability, Analytics
│   │   └── payments/       # Transactions, Crypto Pending Payments
│   ├── voyaga/
│   │   ├── settings.py
│   │   └── urls.py
│   └── manage.py
└── frontend/
    ├── templates/
    │   ├── base.html              # Navbar, Footer, AI Chat, Notifications
    │   ├── index.html             # Homepage
    │   ├── properties.html        # Browse listings
    │   ├── property_detail.html   # Detail + calendar + booking
    │   ├── bookings.html          # My bookings
    │   ├── dashboard.html         # User dashboard
    │   ├── my_listings.html       # Host management
    │   ├── list_property.html     # Create listing
    │   ├── analytics.html         # Host analytics
    │   ├── wishlist.html          # Saved properties
    │   ├── about.html             # Platform info
    │   └── profile.html           # Account settings
    └── static/
        ├── css/main.css
        └── js/app.js
```

---

## ⚙️ Installation

### Prerequisites
- Python 3.11+
- pip

### Steps

```bash
# 1. Clone the repository
git clone <repo-url>
cd voyaga/backend

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate      # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run migrations
python manage.py makemigrations
python manage.py migrate

# 5. Start the server
python manage.py runserver
```

Open **http://localhost:8000**

### Optional: Enable Real AI

Add to `backend/voyaga/settings.py`:
```python
ANTHROPIC_API_KEY = 'sk-ant-your-key-here'
```

Or set as environment variable:
```bash
set ANTHROPIC_API_KEY=sk-ant-...     # Windows
export ANTHROPIC_API_KEY=sk-ant-...  # Mac/Linux
```

> Without a key, the AI chat uses a smart built-in fallback system that still works great.

---

## 🌐 Pages

| URL | Description |
|-----|-------------|
| `/` | Homepage with hero search and recommendations |
| `/properties` | Browse and filter all listings |
| `/property/<id>` | Property detail, availability calendar, booking |
| `/bookings` | My bookings history |
| `/dashboard` | User overview and wallet |
| `/my-listings` | Host property management |
| `/list-property` | Create a new listing |
| `/analytics` | Host earnings and performance dashboard |
| `/wishlist` | Saved / hearted properties |
| `/about` | Platform features overview |
| `/profile` | Account settings |

---

## 🔑 Key API Endpoints

```
POST   /api/auth/register/                   Register
POST   /api/auth/login/                      Login
GET    /api/properties/                      List properties
POST   /api/properties/create/              Create listing
POST   /api/properties/<id>/images/         Upload photos
POST   /api/properties/<id>/delist/         Delist
POST   /api/bookings/initiate/              Start payment
POST   /api/bookings/payment-status/<id>/   Confirm payment
GET    /api/bookings/availability/<id>/     Blocked dates
GET/POST /api/bookings/wishlist/            View / toggle wishlist
GET    /api/bookings/analytics/             Host analytics
POST   /api/auth/chat/                      AI chat
GET    /api/auth/notifications/             Notifications
```

---

## 🔐 Security

- JWT authentication with auto token refresh
- Role-based access: Guest / Host / Admin
- OTP email verification
- PBKDF2 password hashing
- Full audit logging on all bookings and payments
- CSRF protection throughout

---

## 📧 Support

**Email:** help@voyaga.com

---

## 📄 License

MIT — built for educational purposes.

---

<div align="center">
  <strong>Made with 💗 by Team Voyaga(DE)</strong><br><br>
  <em>🔐 Blockchain Secured &nbsp;·&nbsp; 🌱 Carbon Tracked &nbsp;·&nbsp; 🤖 AI Powered</em>
</div>