import axios from 'axios';
import { Household, ScoringConfig, RankingGroup } from './types';

const API_URL = 'http://127.0.0.1:8000';

export const api = axios.create({
    baseURL: API_URL,
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export const login = async (password: string) => {
    const response = await api.post('/token', { password });
    return response.data;
};

export const getHouseholds = async () => {
    const response = await api.get<Household[]>('/households/');
    return response.data;
};

export const getScoringConfig = async () => {
    const response = await api.get<ScoringConfig[]>('/scoring/config');
    return response.data;
};

export const updateScoringConfig = async (configs: ScoringConfig[]) => {
    const response = await api.put('/scoring/config', configs);
    return response.data;
};

export const calculateScores = async () => {
    const response = await api.post('/scoring/calculate');
    return response.data;
};

export const getRanking = async () => {
    const response = await api.get<RankingGroup[]>('/ranking/');
    return response.data;
};

export const uploadHouseholds = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/upload/households/', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};
