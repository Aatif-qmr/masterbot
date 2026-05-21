import type { AxiosResponse } from 'axios';
import axios from 'axios';

import type {
  AuthPayload,
  AuthResponse,
  BotDescriptors,
  AuthStorage,
  AuthStorageMulti,
  BotDescriptor,
} from '@/types';

const AUTH_LOGIN_INFO = 'ftAuthLoginInfo';
const APIBASE = '/api/v1';

// Global state for all login infos
const allLoginInfos = useStorage<AuthStorageMulti>(AUTH_LOGIN_INFO, {});

const MASTER_BOTS = [
  { botName: 'MeanRev', url: 'http://100.90.68.42:8080', username: 'Aatif-qmr', password: '2001' },
  { botName: 'Trend',   url: 'http://100.90.68.42:8081', username: 'Aatif-qmr', password: '2001' },
  { botName: 'Scalp',   url: 'http://100.90.68.42:8082', username: 'Aatif-qmr', password: '2001' },
  { botName: 'Swing',   url: 'http://100.90.68.42:8083', username: 'Aatif-qmr', password: '2001' },
  { botName: 'Daily',   url: 'http://100.90.68.42:8084', username: 'Aatif-qmr', password: '2001' },
  { botName: 'Micro',   url: 'http://100.90.68.42:8085', username: 'Aatif-qmr', password: '2001' },
];

/**
 * Auto-configure the 6 MasterBot instances on first load.
 * No-op if bots are already configured in localStorage.
 */
export async function preConfigureMasterBots(): Promise<void> {
  if (Object.keys(allLoginInfos.value).length > 0) return;

  await Promise.allSettled(
    MASTER_BOTS.map(async (bot, idx) => {
      const botId = `ftbot.${idx}`;
      try {
        const { data } = await axios.post<Record<string, never>, AxiosResponse<AuthResponse>>(
          `${bot.url}/api/v1/token/login`,
          {},
          { auth: { username: bot.username, password: bot.password }, withCredentials: true },
        );
        if (data.access_token && data.refresh_token) {
          allLoginInfos.value[botId] = {
            botName: bot.botName,
            apiUrl: bot.url,
            username: bot.username,
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
            autoRefresh: true,
            sortId: idx,
          };
        }
      } catch {
        // bot offline — skip silently
      }
    }),
  );
}

/**
 * Get available bots with their descriptors
 */
export const loggedInBots = computed<BotDescriptors>(() => {
  const allInfo = allLoginInfos.value;
  const response: BotDescriptors = {};
  Object.keys(allInfo)
    .sort((a, b) => (allInfo[a]?.sortId ?? 0) - (allInfo[b]?.sortId ?? 0))
    .forEach((k, idx) => {
      const bot = allInfo[k];
      if (!bot) return;
      response[k] = {
        botId: k,
        botName: bot.botName,
        botUrl: bot.apiUrl,
        sortId: bot.sortId ?? idx,
      };
    });

  return response;
});

export function useLoginInfo(botId: string) {
  console.log('botId', botId);

  const currentInfo = computed({
    get: () => allLoginInfos.value[botId]!,
    set: (val) => (allLoginInfos.value[botId] = val),
  });

  const autoRefresh = computed({
    get: () => currentInfo.value.autoRefresh,
    set: (val) => (currentInfo.value.autoRefresh = val),
  });
  const accessToken = computed(() => currentInfo.value.accessToken);

  const baseUrl = computed<string>(() => {
    const baseURL = currentInfo.value.apiUrl;
    if (baseURL === null) {
      return APIBASE;
    }
    if (!baseURL.endsWith(APIBASE)) {
      return `${baseURL}${APIBASE}`;
    }
    return `${baseURL}${APIBASE}`;
  });

  const baseWsUrl = computed<string>(() => {
    const baseURL = baseUrl.value;
    if (baseURL.startsWith('http://')) {
      return baseURL.replace('http://', 'ws://');
    }
    if (baseURL.startsWith('https://')) {
      return baseURL.replace('https://', 'wss://');
    }
    return '';
  });

  /**
   * Get login info for current bot
   */
  function getLoginInfo(): AuthStorage {
    const allLoginBot = allLoginInfos.value[botId];
    if (allLoginBot && 'apiUrl' in allLoginBot && 'refreshToken' in allLoginBot) {
      return allLoginBot;
    }
    return {
      botName: '',
      apiUrl: '',
      username: '',
      refreshToken: '',
      accessToken: '',
      autoRefresh: false,
    };
  }

  function updateBot(newValues: Partial<BotDescriptor>): void {
    Object.assign(currentInfo.value, newValues);
  }

  function setRefreshTokenExpired(): void {
    currentInfo.value.refreshToken = '';
    currentInfo.value.accessToken = '';
  }

  function logout(): void {
    console.log('Logging out');
    delete allLoginInfos.value[botId];
  }

  async function loginCall(auth: AuthPayload): Promise<AuthStorage> {
    const { data } = await axios.post<Record<string, never>, AxiosResponse<AuthResponse>>(
      `${auth.url}/api/v1/token/login`,
      {},
      {
        auth: { ...auth },
        withCredentials: true,
      },
    );
    if (data.access_token && data.refresh_token) {
      const obj: AuthStorage = {
        botName: auth.botName,
        apiUrl: auth.url,
        username: auth.username,
        accessToken: data.access_token || '',
        refreshToken: data.refresh_token || '',
        autoRefresh: true,
      };
      return Promise.resolve(obj);
    }
    return Promise.reject('login failed');
  }

  async function login(auth: AuthPayload) {
    const loginInfo = await loginCall(auth);
    currentInfo.value = loginInfo;
  }

  function refreshToken(): Promise<string> {
    console.log('Refreshing token...');
    const token = currentInfo.value.refreshToken;
    return new Promise((resolve, reject) => {
      axios
        .post<Record<string, never>, AxiosResponse<AuthResponse>>(
          `${currentInfo.value.apiUrl}${APIBASE}/token/refresh`,
          {},
          {
            headers: { Authorization: `Bearer ${token}` },
          },
        )
        .then((response) => {
          if (response.data.access_token) {
            currentInfo.value.accessToken = response.data.access_token;
            resolve(response.data.access_token);
          }
        })
        .catch((err) => {
          console.error(err);
          if (err.response && err.response.status === 401) {
            console.log('Refresh token did not refresh.');
            setRefreshTokenExpired();
          } else if (err.response && (err.response.status === 500 || err.response.status === 404)) {
            console.log('Bot seems to be offline... - retrying later');
          }
          reject(err);
        });
    });
  }

  return {
    updateBot,
    getLoginInfo,
    autoRefresh,
    accessToken,
    logout,
    login,
    refreshToken,
    baseUrl,
    baseWsUrl,
  };
}
