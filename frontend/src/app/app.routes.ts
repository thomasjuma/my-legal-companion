import { CanActivateFn, Routes } from '@angular/router';
import { canActivateClerk } from 'ngx-clerk';
import { HomeComponent } from './home/home';
import { ConsultationsComponent } from './consultations/consultations';
import { ChatComponent } from './chat/chat';
import { SignInComponent } from './auth/sign-in/sign-in';
import { SignUpComponent } from './auth/sign-up/sign-up';
import { DashboardComponent } from './dashboard/dashboard';
import { LandingComponent } from './landing/landing';

const auth: CanActivateFn[] = [canActivateClerk];

export const routes: Routes = [
  { path: '', pathMatch: 'full', component: LandingComponent },
  { path: 'sign-in', component: SignInComponent },
  { path: 'sign-up', component: SignUpComponent },
  { path: 'home', component: HomeComponent, canActivate: auth },
  { path: 'dashboard', component: DashboardComponent, canActivate: auth },
  { path: 'consultations', component: ConsultationsComponent, canActivate: auth },
  { path: 'chat', component: ChatComponent, canActivate: auth },
  { path: '**', redirectTo: '' },
];
