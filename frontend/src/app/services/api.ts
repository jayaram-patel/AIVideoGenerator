import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface ProjectCreateResponse {
  project_id: string;
  message: string;
  status: string;
}

export interface ProjectStatus {
  project_id: string;
  status: string;
  total_images: number;
  completed_images: number;
  created_at: string;
}

export interface PipelineProgress {
  project_id: string;
  status: string;
  message: string;
  completed: number;
  total: number;
  error: string | null;
}

@Injectable({
  providedIn: 'root'
})
export class Api {

  private http = inject(HttpClient);
  private baseUrl = 'http://127.0.0.1:8000';

  health(): Observable<{ status: string }> {
    return this.http.get<{ status: string }>(`${this.baseUrl}/health`);
  }

  createProject(
    transcript: string,
    numberOfImages: number,
    characterImage: File
  ): Observable<ProjectCreateResponse> {
    const formData = new FormData();
    formData.append('transcript', transcript);
    formData.append('number_of_images', numberOfImages.toString());
    formData.append('character_image', characterImage);

    return this.http.post<ProjectCreateResponse>(
      `${this.baseUrl}/api/projects/create`,
      formData
    );
  }

  getProjectStatus(projectId: string): Observable<ProjectStatus> {
    return this.http.get<ProjectStatus>(
      `${this.baseUrl}/api/projects/${projectId}/status`
    );
  }

  getProgress(projectId: string): Observable<PipelineProgress> {
    return this.http.get<PipelineProgress>(
      `${this.baseUrl}/api/projects/${projectId}/progress`
    );
  }

  getDownloadUrl(projectId: string): string {
    return `${this.baseUrl}/api/projects/${projectId}/download`;
  }
}