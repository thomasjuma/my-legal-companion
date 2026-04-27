import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ClerkSignUpComponent, type SignUpProps } from 'ngx-clerk';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-sign-up',
  imports: [ClerkSignUpComponent, RouterLink],
  templateUrl: './sign-up.html',
  styleUrl: './sign-up.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SignUpComponent {
  protected readonly signUpProps: SignUpProps = {
    routing: 'path',
    path: environment.clerkSignUpPath,
    fallbackRedirectUrl: environment.afterSignUpPath,
    signInUrl: environment.clerkSignInPath,
  };
}
