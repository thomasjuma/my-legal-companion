import { CommonModule } from '@angular/common';
import { Component, ElementRef, ViewChild, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ChatService } from '../services/chat.service';
import { httpErrorMessage } from '../core/http-error-message';
import { ChatMessage } from '../models/api.models';

type Turn = ChatMessage & { key: number };

@Component({
  selector: 'app-chat',
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.html',
  styleUrl: './chat.css',
})
export class ChatComponent {
  private readonly api = inject(ChatService);
  private seq = 0;

  @ViewChild('scrollArea') private scrollArea?: ElementRef<HTMLElement>;

  protected readonly transcript = signal<Turn[]>([]);
  protected readonly draft = signal('');
  protected readonly sending = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly lastModel = signal<string | null>(null);

  protected send(): void {
    const text = this.draft().trim();
    if (!text || this.sending()) return;

    this.error.set(null);
    const userMsg: Turn = {
      key: this.seq++,
      role: 'user',
      content: text,
    };
    this.transcript.update((t) => [...t, userMsg]);
    this.draft.set('');
    this.sending.set(true);
    queueMicrotask(() => this.scrollToBottom());

    const payload: ChatMessage[] = this.transcript().map(({ role, content }) => ({
      role,
      content,
    }));

    this.api.sendMessage({ messages: payload }).subscribe({
      next: (res) => {
        this.lastModel.set(res.model);
        this.transcript.update((t) => [
          ...t,
          { key: this.seq++, role: 'assistant', content: res.message },
        ]);
      },
      error: (e) => {
        this.error.set(httpErrorMessage(e));
        this.transcript.update((t) => t.slice(0, -1));
        this.draft.set(text);
      },
      complete: () => {
        this.sending.set(false);
        queueMicrotask(() => this.scrollToBottom());
      },
    });
  }

  protected onComposerKeydown(ev: KeyboardEvent): void {
    if (ev.key === 'Enter' && !ev.shiftKey) {
      ev.preventDefault();
      this.send();
    }
  }

  private scrollToBottom(): void {
    const el = this.scrollArea?.nativeElement;
    if (el) el.scrollTop = el.scrollHeight;
  }
}
