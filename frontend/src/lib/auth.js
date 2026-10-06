import { cognitoConfigured, isDemoMode } from "./config";

const config = {
  UserPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID,
  ClientId: import.meta.env.VITE_COGNITO_CLIENT_ID
};

const ROLE_NAMES = ["CITIZEN", "FARMER", "MUNICIPAL_WORKER", "MUNICIPAL_OFFICER", "RECOVERY_PARTNER", "ADMIN"];
let poolPromise;
const DEMO_SESSION_KEY = "kasamukti-demo-session";
const DEMO_NOTIFICATION_KEY = "kasamukti-demo-notifications";
const DEMO_NAMES = {
  CITIZEN: "Demo Citizen",
  FARMER: "Demo Farmer",
  MUNICIPAL_WORKER: "Demo Municipal Worker",
  MUNICIPAL_OFFICER: "Demo Municipal Officer",
  RECOVERY_PARTNER: "Demo Recovery Partner",
  ADMIN: "Demo Administrator"
};

async function getPool() {
  if (!config.UserPoolId || !config.ClientId) return null;
  if (!poolPromise) {
    poolPromise = import("amazon-cognito-identity-js").then(({ CognitoUserPool }) => new CognitoUserPool(config));
  }
  return poolPromise;
}

async function currentUser() {
  return (await getPool())?.getCurrentUser() || null;
}

export function authConfigured() {
  return isDemoMode || cognitoConfigured;
}

export function getDemoSession() {
  if (!isDemoMode) return null;
  try {
    return JSON.parse(localStorage.getItem(DEMO_SESSION_KEY) || "null");
  } catch {
    return null;
  }
}

export function signInDemo(role = "CITIZEN", email = "") {
  if (!isDemoMode) throw new Error("Demo authentication is disabled in live mode.");
  const normalizedRole = ROLE_NAMES.includes(role) ? role : "CITIZEN";
  const identity = {
    userId: `demo-${normalizedRole.toLowerCase()}-${crypto.randomUUID().slice(0, 8)}`,
    name: DEMO_NAMES[normalizedRole],
    email: email.trim() || `${normalizedRole.toLowerCase()}@example.com`,
    role: normalizedRole,
    location: "Ward 12, Hyderabad",
    greenPoints: 0,
    demo: true
  };
  localStorage.setItem(DEMO_SESSION_KEY, JSON.stringify(identity));
  const notification = {
    notificationId: `demo-notification-${crypto.randomUUID().slice(0, 8)}`,
    userId: identity.userId,
    type: "ACCOUNT_WELCOME",
    channel: "EMAIL",
    recipient: identity.email,
    subject: "Welcome to KasaMukti",
    status: "SIMULATED",
    createdAt: new Date().toISOString(),
    label: "DEMO EMAIL"
  };
  localStorage.setItem(DEMO_NOTIFICATION_KEY, JSON.stringify(notification));
  return identity;
}

export function clearDemoSession() {
  localStorage.removeItem(DEMO_SESSION_KEY);
}

export async function getSession() {
  if (isDemoMode) return getDemoSession();
  const user = await currentUser();
  return new Promise((resolve, reject) => {
    if (!user) return resolve(null);
    user.getSession((error, session) => {
      if (error) return reject(error);
      if (!session?.isValid()) return resolve(null);
      const payload = session.getIdToken().decodePayload();
      const groups = payload["cognito:groups"] || [];
      const role = ROLE_NAMES.find((candidate) => groups.includes(candidate)) || "CITIZEN";
      resolve({ user, session, userId: payload.sub, email: payload.email, role, groups });
    });
  });
}

export async function signIn(email, password) {
  if (isDemoMode) return signInDemo("CITIZEN", email);
  const pool = await getPool();
  return new Promise((resolve, reject) => {
    if (!pool) return reject(new Error("Cognito is not configured. Set VITE_COGNITO_USER_POOL_ID and VITE_COGNITO_CLIENT_ID."));
    import("amazon-cognito-identity-js").then(({ AuthenticationDetails, CognitoUser }) => {
      const user = new CognitoUser({ Username: email, Pool: pool });
      user.authenticateUser(new AuthenticationDetails({ Username: email, Password: password }), {
      onSuccess: () => getSession().then(resolve).catch(reject),
      onFailure: reject,
      });
    }).catch(reject);
  });
}

export async function signUp(email, password, role = "CITIZEN") {
  const pool = await getPool();
  return new Promise((resolve, reject) => {
    if (!pool) return reject(new Error("Cognito is not configured."));
    import("amazon-cognito-identity-js").then(({ CognitoUserAttribute }) => pool.signUp(email, password, [new CognitoUserAttribute({ Name: "email", Value: email })], null, (error, result) => {
      if (error) return reject(error);
      resolve({ user: result.user, role });
    })).catch(reject);
  });
}

export async function confirmSignUp(email, code) {
  const pool = await getPool();
  return new Promise((resolve, reject) => {
    if (!pool) return reject(new Error("Cognito is not configured."));
    import("amazon-cognito-identity-js").then(({ CognitoUser }) => {
      new CognitoUser({ Username: email, Pool: pool }).confirmRegistration(code, true, (error, result) => {
        if (error) return reject(error);
        resolve(result);
      });
    }).catch(reject);
  });
}

export async function forgotPassword(email) {
  const pool = await getPool();
  return new Promise((resolve, reject) => {
    if (!pool) return reject(new Error("Cognito is not configured."));
    import("amazon-cognito-identity-js").then(({ CognitoUser }) => {
      new CognitoUser({ Username: email, Pool: pool }).forgotPassword({
        onSuccess: resolve,
        onFailure: reject
      });
    }).catch(reject);
  });
}

export async function signOut() {
  const user = await currentUser();
  user?.signOut();
}

export async function accessToken() {
  const session = await getSession();
  return session?.session.getIdToken().getJwtToken() || "";
}
