import { Routes } from '@angular/router';
import { HomeComponent } from './home/home';
import { ConsultationsComponent } from './consultations/consultations';
import { ChatComponent } from './chat/chat';

export const routes: Routes = [
  { path: '', component: HomeComponent },
  { path: 'consultations', component: ConsultationsComponent },
  { path: 'chat', component: ChatComponent },
  { path: '**', redirectTo: '' },
];
