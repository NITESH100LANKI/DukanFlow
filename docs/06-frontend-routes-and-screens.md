# 06 — Frontend Routes and Screen Plan

## 1. Routing Architecture

```
/                       → Redirect to /login (unauthenticated) or home (authenticated)
/login                  → Shared login page (role determined after auth)
/retailer/*             → Retailer layout (requires retailer JWT)
/desk/*                 → Order Desk layout (requires order_desk JWT)
```

Route guards:
- `<RetailerRoute>` — redirects to `/login` if not authenticated or not a retailer.
- `<DeskRoute>` — redirects to `/login` if not authenticated or not `order_desk`.
- Role is derived from the JWT `role` claim.

---

## 2. Screen Inventory

### 2.1 Public Screens

| Route | Screen | Description |
|-------|--------|-------------|
| `/login` | **Login** | Mobile OTP flow for retailers; email+password for Order Desk. Toggle between modes. |
| `/login/otp` | **OTP Verification** | 6-digit OTP entry. Countdown timer (10 min). Resend option after 60 s. |

---

### 2.2 Retailer Screens

| Route | Screen | Description |
|-------|--------|-------------|
| `/retailer` | **Retailer Home** | Shortcut cards: Browse Catalogue, My Orders, AI Order. Balance/credit info banner if credit limit is set. |
| `/retailer/catalogue` | **Product Catalogue** | Paginated grid of products. Search bar, in-stock filter, category filter. Each card shows product info + scheme badge + Add to Cart button (disabled if out of stock). |
| `/retailer/catalogue/:sku` | **Product Detail** | Enlarged product view with full scheme details and quantity selector. |
| `/retailer/cart` | **Cart** | Line items table with qty controls, scheme savings shown per line, order summary panel. Remarks input. Place Order CTA. |
| `/retailer/orders` | **My Orders** | Paginated list of this retailer's orders. Status chips (colour-coded). Click to expand. |
| `/retailer/orders/:id` | **Order Detail** | Full order with line items, totals, status, rejection reason if applicable, audit trail. Cancel button (shown only if `pending_review`). |
| `/retailer/ai-capture` | **AI Order Capture** | Text area for pasting WhatsApp message. Submit triggers AI extraction. Renders draft results below. |
| `/retailer/ai-capture/review` | **AI Draft Review** | Line-by-line review of AI output. Ambiguous items show alternative selectors. Unclear units show unit selector. Out-of-stock items shown with warning and cannot be sent to cart. Send to Cart CTA. |

---

### 2.3 Order Desk Screens

| Route | Screen | Description |
|-------|--------|-------------|
| `/desk` | **Desk Dashboard** | Summary cards: orders pending review, approved today, rejected today. Quick-access to order queue. |
| `/desk/orders` | **Order Queue** | Paginated list of orders, default-sorted by `created_at` ASC (oldest first). Filters: status, retailer search, date range. |
| `/desk/orders/:id` | **Order Review** | Full order detail with inline edit controls for qty per line. Add line from catalogue. Remove line. Approve / Reject action buttons. |
| `/desk/orders/:id/export` | **Export Preview** | Preview of Tally CSV data for this order. Download CSV button. |
| `/desk/export/batch` | **Batch Export** | Multi-select approved orders, download combined CSV. |

---

## 3. Component Structure (High-Level)

```
src/
├── App.tsx                    # Router setup, auth context provider
├── contexts/
│   └── AuthContext.tsx        # JWT state, login/logout, role
├── hooks/
│   ├── useAuth.ts
│   ├── useCart.ts
│   ├── useCatalogue.ts
│   └── useOrders.ts
├── api/
│   ├── client.ts              # Axios instance, interceptor for token refresh
│   ├── auth.ts
│   ├── catalogue.ts
│   ├── cart.ts
│   ├── orders.ts
│   ├── ai.ts
│   └── export.ts
├── layouts/
│   ├── RetailerLayout.tsx     # Nav, header, mobile-friendly shell
│   └── DeskLayout.tsx         # Sidebar nav for desktop-first desk view
├── pages/
│   ├── Login/
│   ├── OtpVerify/
│   ├── retailer/
│   │   ├── Home/
│   │   ├── Catalogue/
│   │   ├── ProductDetail/
│   │   ├── Cart/
│   │   ├── Orders/
│   │   ├── OrderDetail/
│   │   ├── AiCapture/
│   │   └── AiDraftReview/
│   └── desk/
│       ├── Dashboard/
│       ├── OrderQueue/
│       ├── OrderReview/
│       ├── ExportPreview/
│       └── BatchExport/
├── components/
│   ├── ui/                    # Primitives: Button, Badge, Input, Modal, Spinner
│   ├── ProductCard.tsx
│   ├── CartLine.tsx
│   ├── OrderStatusChip.tsx
│   ├── SchemeBadge.tsx
│   ├── AiDraftLine.tsx        # Renders one AI-extracted line with controls
│   ├── AlternativeSelector.tsx
│   └── UnitClarifier.tsx
└── utils/
    ├── formatCurrency.ts
    └── formatDate.ts
```

---

## 4. Screen Wireframes (Text Descriptions)

### 4.1 Retailer — AI Capture Screen (`/retailer/ai-capture`)

```
┌───────────────────────────────────────────────────┐
│  🤖  AI Order Capture                             │
│                                                   │
│  Paste your WhatsApp order message below:         │
│  ┌─────────────────────────────────────────────┐  │
│  │ bhaiya 5 peti biscuit chhota,               │  │
│  │ 2 peti washing powder 1 kilo,               │  │
│  │ chai patti 250 wala 1 peti                  │  │
│  └─────────────────────────────────────────────┘  │
│                                                   │
│  [ Extract Products →  ]                          │
│                                                   │
│  ⚠ AI creates a draft only. You review before    │
│    sending to cart.                               │
└───────────────────────────────────────────────────┘
```

### 4.2 Retailer — AI Draft Review Screen (`/retailer/ai-capture/review`)

```
┌────────────────────────────────────────────────────────────┐
│  Review Your AI Draft                                      │
├────────────────────────────────────────────────────────────┤
│  "5 peti biscuit chhota"   → ✅ Glucose Biscuit 75g        │
│  Qty: 5 cases  |  ₹8.10/case  |  Scheme: Buy 10 Get 1 Free│
│                                                            │
│  "2 peti washing powder 1 kilo" → ✅ Detergent Powder 1kg  │
│  Qty: 2 cases  |  ₹101.50/case  |  Scheme: 3% off ≥5 cases│
│                                                            │
│  "chai patti 250 wala 1 peti" → ⚠ Tea Leaf 250g           │
│  ❌ OUT OF STOCK — Cannot be added to cart.                │
│  [ Remove ] [ Find Substitute from Catalogue ]             │
│                                                            │
├────────────────────────────────────────────────────────────┤
│  [ ← Edit Message ]        [ Send to Cart (2 items) → ]   │
└────────────────────────────────────────────────────────────┘
```

### 4.3 AI Draft — Ambiguous Match (Inline)

```
│  "biscuit" → ⚠ Ambiguous — which product?                 │
│  ○ Glucose Biscuit 75g (SKU-BS-075)  — ₹8.10/pack         │
│  ○ Cream Biscuit 100g (SKU-BC-100)   — ₹12.00/pack        │
│  [ Search Catalogue for a different product ]              │
```
*(At most 2 alternatives are shown.)*

### 4.4 AI Draft — Unit Unclear (Inline)

```
│  "2 biscuit" → ❓ Unit unclear                             │
│  Is this:                                                  │
│  ○ 2 Cases (192 pieces)                                    │
│  ○ 2 Pieces                                                │
│  Please select to continue.                                │
```

---

## 5. UI/UX Notes

| Concern | Decision |
|---------|----------|
| Mobile-first | Retailer screens are mobile-first (they use phones). Desk screens are desktop-first. |
| Language | Retailer-facing UI must support **Hindi and English**. Static labels (buttons, headings, errors) are bilingual or switchable. Product names from the database may be in either language. The language toggle is a top-level control in the retailer layout header. |
| Touch targets | All interactive elements on retailer screens have a minimum touch target of **48 × 48 px** (following WCAG 2.5.5 / Google Material guidelines). This is critical for kirana shop owners on small-screen Android phones. |
| Low-network performance | Retailer screens must function on 3G / poor 4G connections. Requirements: (a) Paginated lists — max 20 items per page. (b) Images avoided; icons use SVG or CSS. (c) Bundle size target < 200 KB gzipped for the initial JS chunk. (d) API calls show immediate loading state; no blank screens. (e) Cart state cached locally (React state + session storage) to survive brief network drops. |
| Main screen count | 6–8 primary screen experiences for retailers (as listed in section 2.2). Avoid deep navigation trees. |
| Loading states | All async operations show a spinner / skeleton. No silent waits. |
| Error messages | All errors shown inline near the action that caused them, not just toast notifications. |
| Monetary display | `₹` prefix, 2 decimal places, e.g., `₹8.10`. Formatted with `Intl.NumberFormat('en-IN', { currency: 'INR' })`. |
| Out-of-stock visual | Red badge `OUT OF STOCK` on product cards. Add to Cart button is disabled + greyed. |
| Scheme visual | Green badge `SCHEME ACTIVE` on product cards. Free cases shown in green (not as "savings"). Discount amount shown in green. |
| Pagination | All lists paginated; no infinite scroll for MVP. |
| Scheme display | For `BUY_N_GET_M_FREE`: show "Get 1 FREE case on 10 cases ordered" (not "Save ₹X"). For `DISCOUNT_ON_MIN_QTY`: show "3% off on 5+ cases — Save ₹304.50". |

