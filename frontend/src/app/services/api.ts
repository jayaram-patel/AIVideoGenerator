import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({
  providedIn: 'root'
})
export class Api {

  private http = inject(HttpClient);

  private baseUrl = 'http://127.0.0.1:8000';

  health() {
    return this.http.get<{ status: string }>(
      `${this.baseUrl}/health`
    );
  }
}