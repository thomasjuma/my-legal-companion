import { Routes } from '@angular/router';
import { canActivateClerk } from 'ngx-clerk';
import { HomeComponent } from './home/home';
import { ConsultationsComponent } from './consultations/consultations';
import { ChatComponent } from './chat/chat';
import { SignInComponent } from './auth/sign-in/sign-in';
import { SignUpComponent } from './auth/sign-up/sign-up';
import { DashboardComponent } from './dashboard/dashboard';

export const routes: Routes = [
  { path: '', component: HomeComponent },
  { path: 'sign-in', component: SignInComponent },
  { path: 'sign-up', component: SignUpComponent },
  {
    path: 'dashboard',
    component: DashboardComponent,
    canActivate: [canActivateClerk],
  },
  { path: 'consultations', component: ConsultationsComponent },
  { path: 'chat', component: ChatComponent },
  { path: '**', redirectTo: '' },
];
