# Adaptive IoT Sensing — Dashboard Frontend

React + Vite + Tailwind implementation of the 3-page dashboard
(Live Monitoring, Trial Results, Trial History), matching the approved
mockups.

## Setup

```bash
npm install
npm run dev
```

Open the printed local URL (typically http://localhost:5173).

## Build for production

```bash
npm run build
npm run preview
```

## Current data source

All three pages currently render from `src/data/mockData.js` — static
sample data matching the approved mockups, so the UI is fully viewable
and interactive without any backend running.

## Wiring up the real backend

Once `backend/api/server.py` (see `PROTOTYPE_PLAN.md`) is running
against MongoDB, replace the imports from `mockData.js` in each page
(`src/pages/Live.jsx`, `Results.jsx`, `History.jsx`) with `fetch()` calls
to the API, e.g.:

```js
useEffect(() => {
  fetch("http://localhost:8000/trials")
    .then((r) => r.json())
    .then(setTrials);
}, []);
```

The data shapes in `mockData.js` were written to match the MongoDB
schema in `PROTOTYPE_PLAN.md` Section 3, so the swap should be close to
a drop-in replacement.

## Logo

`public/logo.png` is the project logo with a transparent background,
referenced directly in `src/components/Navbar.jsx` and as the browser
favicon in `index.html`.
