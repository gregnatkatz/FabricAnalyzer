import { PublicClientApplication } from '@azure/msal-browser';

// Default config — can be overridden at runtime via setClientConfig()
let runtimeClientId = import.meta.env.VITE_MSAL_CLIENT_ID || '';
let runtimeTenantId = import.meta.env.VITE_MSAL_TENANT_ID || 'common';

function buildMsalConfig() {
  return {
    auth: {
      clientId: runtimeClientId,
      authority: `https://login.microsoftonline.com/${runtimeTenantId}`,
      redirectUri: window.location.origin,
    },
    cache: {
      // In-memory only — never use localStorage or sessionStorage
      cacheLocation: 'memoryStorage',
    },
  };
}

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

/**
 * Set Client ID and Tenant ID at runtime from the UI.
 * Resets any existing MSAL instance so the next login uses new config.
 */
export function setClientConfig(clientId, tenantId) {
  runtimeClientId = clientId;
  runtimeTenantId = tenantId || 'common';
  msalInstance = null; // force re-creation with new config
}

export function getClientConfig() {
  return { clientId: runtimeClientId, tenantId: runtimeTenantId };
}

export function getMsalInstance() {
  if (!msalInstance) {
    if (!runtimeClientId) {
      throw new Error('Client ID not configured. Paste your App Registration Client ID in the Quick Setup section.');
    }
    msalInstance = new PublicClientApplication(buildMsalConfig());
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

export { loginRequest, fabricScopes };
