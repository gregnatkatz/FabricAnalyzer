import { PublicClientApplication } from '@azure/msal-browser';

const msalConfig = {
  auth: {
    clientId: import.meta.env.VITE_MSAL_CLIENT_ID || '',
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_MSAL_TENANT_ID || 'common'}`,
    redirectUri: window.location.origin,
  },
  cache: {
    // In-memory only — never use localStorage or sessionStorage
    cacheLocation: 'memoryStorage',
  },
};

const loginRequest = {
  scopes: [
    'https://analysis.windows.net/powerbi/api/.default',
  ],
};

const fabricScopes = {
  scopes: [
    'https://analysis.windows.net/powerbi/api/Dataset.Read.All',
    'https://analysis.windows.net/powerbi/api/Capacity.Read.All',
    'offline_access',
  ],
};

let msalInstance = null;

export function getMsalInstance() {
  if (!msalInstance) {
    msalInstance = new PublicClientApplication(msalConfig);
  }
  return msalInstance;
}

export async function loginPopup() {
  const instance = getMsalInstance();
  await instance.initialize();
  const response = await instance.loginPopup(loginRequest);
  return response;
}

export async function getAccessToken() {
  const instance = getMsalInstance();
  const accounts = instance.getAllAccounts();
  if (accounts.length === 0) {
    throw new Error('No accounts found — user must sign in first');
  }
  try {
    const response = await instance.acquireTokenSilent({
      ...fabricScopes,
      account: accounts[0],
    });
    return response.accessToken;
  } catch (err) {
    const response = await instance.acquireTokenPopup(fabricScopes);
    return response.accessToken;
  }
}

export async function logout() {
  const instance = getMsalInstance();
  await instance.logoutPopup();
}

export { msalConfig, loginRequest, fabricScopes };
