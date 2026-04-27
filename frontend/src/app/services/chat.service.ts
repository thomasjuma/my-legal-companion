import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { apiPath } from '../core/api-path';
import { ChatRequest, ChatResponse } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class ChatService {
  private readonly http = inject(HttpClient);

  sendMessage(body: ChatRequest) {
    return this.http.post<ChatResponse>(apiPath('/api/chat/messages'), body);
  }
}
