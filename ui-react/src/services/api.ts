import axios from "axios";
//import { toast } from 'react-toastify'; нужно ставить чтобы приходили уведы пользователю

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8901/api";
export const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error("API Error:", error);
    //toast.error('Ошибка при запросе к серверу');
    return Promise.reject(error);
  }
);
