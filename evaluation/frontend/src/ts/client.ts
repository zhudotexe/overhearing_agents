import { Notifications } from "@/ts/notifications";
import axios from "axios";
import { API_BASE } from "./constants";

// On error, automatically add an error notification to Notifications.
axios.interceptors.request.use(
  // noop on success
  (response) => response,
  function (error) {
    Notifications.error(error.message);
    return Promise.reject(error);
  },
);

axios.interceptors.response.use(
  // noop on success
  (response) => response,
  // send httpError to notifications on error
  function (error) {
    Notifications.httpError(error);
    return Promise.reject(error);
  },
);

export class EvalClient {
  username: string | null = null;
  assignments: any[] = [];

  // session management
  public isLoggedIn(): boolean {
    return this.username !== null;
  }

  public logout() {
    this.username = null;
    this.assignments = [];
  }

  public async login(username: string) {
    const payload = { username };
    const response = await axios.post(`${API_BASE}/login`, payload);
    const data = response.data;
    this.username = data.username;
    this.assignments = data.assignments;
    return data;
  }

  public async getExperiments() {
    const response = await axios.get(`${API_BASE}/experiments`);
    return response.data;
  }

  public async getClassifications() {
    const response = await axios.get(`${API_BASE}/classifications`);
    return response.data;
  }

  public async getNextIncompleteAnnotation(experimentId: string) {
    const response = await axios.get(`${API_BASE}/next-annotation`, {
      params: {
        username: this.username,
        experiment_id: experimentId,
      },
    });
    return response.data;
  }

  public async getExperimentTranscript(experimentId: string, start: number, end: number) {
    const response = await axios.get(`${API_BASE}/${experimentId}/transcript`, {
      params: { start, end },
    });
    return response.data;
  }

  public getExperimentAudioSrc(experimentId: string, start: number, end: number) {
    return `${API_BASE}/${experimentId}/audio?start=${start}&end=${end}`;
  }

  public async postAnnotation(
    experimentId: string,
    suggestionId: string,
    score: number,
    labels: string[],
    contextStart: number,
    contextEnd: number,
    comment: string = "",
    applyToRest: boolean = false,
    applyToAllNPC: boolean = false,
    bulkApplyDuration: number = 99999,
  ) {
    const payload = {
      username: this.username,
      experiment_id: experimentId,
      suggestion_id: suggestionId,
      score,
      labels,
      context_start: contextStart,
      context_end: contextEnd,
      comment,
      apply_to_rest: applyToRest,
      apply_to_all_of_npc: applyToAllNPC,
      bulk_apply_duration: bulkApplyDuration,
    };
    const response = await axios.post(`${API_BASE}/annotation`, payload);
    return response.data;
  }
}
