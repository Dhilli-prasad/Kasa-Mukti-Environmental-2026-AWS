const env = import.meta.env;

export const isDemoMode = env.VITE_DEMO_MODE === "true";
export const apiBaseUrl = (env.VITE_API_BASE_URL || "").replace(/\/$/, "");
export const isLiveApiConfigured = !isDemoMode && Boolean(apiBaseUrl);
export const cognitoConfigured = Boolean(env.VITE_COGNITO_USER_POOL_ID && env.VITE_COGNITO_CLIENT_ID);
export const sesConfigured = !isDemoMode && env.VITE_SES_ENABLED === "true" && Boolean(env.VITE_SES_SENDER_EMAIL);
