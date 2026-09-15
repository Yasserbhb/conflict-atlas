// Who is looking at this page — a visitor, or the person who maintains the atlas.
//
// This is a CLARITY boundary, not a security one, and it's worth being honest about which:
// every edit this app makes lands in the viewer's own IndexedDB and never leaves their
// browser, so a visitor reaching Edit cannot alter the published dataset or anyone else's
// copy. The problem it solves is that an Edit button implies "contribute here" when nothing
// a visitor types will ever reach the atlas. Hiding it makes the site honest about what it is:
// something to read.
//
// Anything that genuinely needs protecting must be protected on a server. There isn't one —
// the site is static — so nothing secret may ever be placed behind this flag.

const KEY = 'conflict-atlas:maintainer';

function readStored() {
  try {
    return localStorage.getItem(KEY) === '1';
  } catch {
    return false;            // private mode, blocked storage — treat as a visitor
  }
}

function store(on) {
  try {
    if (on) localStorage.setItem(KEY, '1');
    else localStorage.removeItem(KEY);
  } catch {
    /* nothing to do — the URL flag still covers this page load */
  }
}

/**
 * True when maintainer-only surfaces (Edit mode, the Pipeline view) should be available.
 *
 *   - `npm run dev`      always on. This is where data is actually authored, so the toggle
 *                        should never be in the way there.
 *   - deployed build     off by default. `?maintainer=1` turns it on and remembers it on this
 *                        browser; `?maintainer=0` turns it back off.
 */
export function isMaintainer() {
  if (import.meta.env.DEV) return true;

  let flag = null;
  try {
    flag = new URLSearchParams(window.location.search).get('maintainer');
  } catch {
    /* no window/search (SSR, tests) — fall through to stored value */
  }

  if (flag === '1') {
    store(true);
    return true;
  }
  if (flag === '0') {
    store(false);
    return false;
  }
  return readStored();
}
