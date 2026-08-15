/**
 * Build-time deployment mode.
 *
 * GitHub Pages is static hosting — there is no Python runtime, so the Flask
 * engine cannot run alongside the SPA. In that build the app reads the
 * precomputed analysis bundled at build time instead of calling /api, and says
 * so in the UI rather than showing an error.
 *
 * Set VITE_STATIC_DEMO=true in the Pages workflow. Vercel and local dev leave
 * it unset and talk to the live API.
 */
export const STATIC_DEMO = import.meta.env.VITE_STATIC_DEMO === "true";

/** Where to point people who want the parts a static host cannot serve. */
export const REPO_URL = "https://github.com/parthpatel2211/FraudDetectionAgent";
