import axios from 'axios';
import {
    Household,
    ScoringConfig,
    RankingGroup,
    Person,
    PersonWithHousehold,
    HHAnalysisResponse,
    HHCommitRequest,
    HHCommitResponse,
    IndividualAnalysisResponse,
    IndividualCommitRequest,
    IndividualCommitResponse,
} from './types';

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

export const getHousehold = async (id: number) => {
    const response = await api.get<Household>(`/households/${id}`);
    return response.data;
};

export const updateHousehold = async (id: number, data: Partial<Household>) => {
    const response = await api.put<Household>(`/households/${id}`, data);
    return response.data;
};

export const updatePerson = async (id: number, data: Partial<Person>) => {
    const response = await api.put<Person>(`/people/${id}`, data);
    return response.data;
};

export const assignPerson = async (personId: number, householdId: number) => {
    const response = await api.post(`/people/${personId}/assign/${householdId}`);
    return response.data;
};

export const getAllPersons = async () => {
    const response = await api.get<PersonWithHousehold[]>('/people/');
    return response.data;
};

export const getUnassignedPersons = async () => {
    const response = await api.get<Person[]>('/people/unassigned');
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
        headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
};

// --- Import API ---

export const analyzeHHBogen = async (file: File): Promise<HHAnalysisResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<HHAnalysisResponse>('/import/household-bogen/analyze', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
};

export const commitHHBogen = async (request: HHCommitRequest): Promise<HHCommitResponse> => {
    const response = await api.post<HHCommitResponse>('/import/household-bogen/commit', request);
    return response.data;
};

export const analyzeIndividualBogen = async (file: File): Promise<IndividualAnalysisResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<IndividualAnalysisResponse>('/import/individual-bogen/analyze', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
};

export const commitIndividualBogen = async (request: IndividualCommitRequest): Promise<IndividualCommitResponse> => {
    const response = await api.post<IndividualCommitResponse>('/import/individual-bogen/commit', request);
    return response.data;
};
