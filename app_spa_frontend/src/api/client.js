import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 20000,
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    const message =
      error.code === 'ECONNABORTED'
        ? 'Сервер не отвечает. Проверьте подключение.'
        : error.response?.data?.detail ||
          error.response?.data?.message ||
          error.message ||
          'Ошибка сети';
    return Promise.reject({ ...error, friendlyMessage: message });
  }
);

export default api;
