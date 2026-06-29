import { Component, inject, signal, computed, OnDestroy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { Api } from '../services/api';
import { interval, Subscription } from 'rxjs';
import { switchMap, takeWhile } from 'rxjs/operators';

export type Status = 'idle' | 'uploading' | 'generating' | 'completed' | 'error';

@Component({
  selector: 'app-dashboard',
  imports: [FormsModule, CommonModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css'
})
export class Dashboard implements OnDestroy {

  private api = inject(Api);
  private pollSub: Subscription | null = null;

  // ─── Inputs ───
  transcript = signal('');
  characterImage = signal<File | null>(null);
  characterImagePreview = signal<string | null>(null);
  numberOfImages = signal(10);

  // ─── State ───
  status = signal<Status>('idle');
  statusMessage = signal('');
  completedImages = signal(0);
  totalImages = signal(10);
  projectId = signal<string | null>(null);

  // ─── Computed ───
  canGenerate = computed(() => {
    const s = this.status();
    return (
      this.transcript().trim().length > 20 &&
      this.characterImage() !== null &&
      (s === 'idle' || s === 'error' || s === 'completed')
    );
  });

  isProcessing = computed(() => {
    const s = this.status();
    return s === 'uploading' || s === 'generating';
  });

  progressPercent = computed(() => {
    const total = this.totalImages();
    const done = this.completedImages();
    if (total === 0) return 0;
    return Math.round((done / total) * 100);
  });

  // ─── Character Image ───
  onImageSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      const file = input.files[0];
      const valid = ['image/png', 'image/jpeg', 'image/jpg'];
      if (valid.includes(file.type)) {
        this.characterImage.set(file);
        const reader = new FileReader();
        reader.onload = () => this.characterImagePreview.set(reader.result as string);
        reader.readAsDataURL(file);
      } else {
        alert('Please upload a .png or .jpg image');
      }
    }
  }

  removeImage(): void {
    this.characterImage.set(null);
    this.characterImagePreview.set(null);
  }

  // ─── Transcript file upload ───
  onTranscriptFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      const file = input.files[0];
      if (file.name.endsWith('.txt')) {
        const reader = new FileReader();
        reader.onload = () => this.transcript.set(reader.result as string);
        reader.readAsText(file);
      } else {
        alert('Please upload a .txt file');
      }
    }
  }

  // ─── Generate ───
  generate(): void {
    if (!this.canGenerate()) return;

    // Stop any existing poll
    this.stopPolling();

    this.status.set('uploading');
    this.statusMessage.set('Creating project...');
    this.completedImages.set(0);
    this.totalImages.set(this.numberOfImages());

    this.api.createProject(
      this.transcript(),
      this.numberOfImages(),
      this.characterImage()!
    ).subscribe({
      next: (res) => {
        this.projectId.set(res.project_id);
        this.status.set('generating');
        this.statusMessage.set('AI is splitting transcript into scenes...');
        // Start polling every 2 seconds
        this.startPolling(res.project_id);
      },
      error: (err) => {
        this.status.set('error');
        const detail = err?.error?.detail || err?.message || 'Network error — is the backend running?';
        this.statusMessage.set(detail);
      }
    });
  }

  // ─── Progress Polling ───
  private startPolling(projectId: string): void {
    this.pollSub = interval(2000).pipe(
      switchMap(() => this.api.getProgress(projectId)),
      takeWhile(
        (prog) => prog.status !== 'completed' && prog.status !== 'error',
        true  // emit the terminal value too
      )
    ).subscribe({
      next: (prog) => {
        this.completedImages.set(prog.completed);
        this.totalImages.set(prog.total || this.numberOfImages());
        this.statusMessage.set(prog.message);

        if (prog.status === 'completed') {
          this.status.set('completed');
          this.statusMessage.set(`✅ All ${prog.total} images generated!`);
          this.stopPolling();
        } else if (prog.status === 'error') {
          this.status.set('error');
          this.statusMessage.set(prog.error || 'Generation failed');
          this.stopPolling();
        } else {
          this.status.set('generating');
        }
      },
      error: (err) => {
        // Poll HTTP error — keep trying silently for 3 more attempts then give up
        console.error('Poll error:', err);
      }
    });
  }

  private stopPolling(): void {
    if (this.pollSub) {
      this.pollSub.unsubscribe();
      this.pollSub = null;
    }
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  // ─── Download ───
  download(): void {
    const id = this.projectId();
    if (!id) return;
    window.open(this.api.getDownloadUrl(id), '_blank');
  }
}