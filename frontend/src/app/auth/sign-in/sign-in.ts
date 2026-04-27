import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ClerkSignInComponent, type SignInProps } from 'ngx-clerk';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-sign-in',
  imports: [ClerkSignInComponent, RouterLink],
  templateUrl: './sign-in.html',
  styleUrl: './sign-in.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SignInComponent {
  protected readonly signInProps: SignInProps = {
    routing: 'path',
    path: environment.clerkSignInPath,
    fallbackRedirectUrl: environment.afterSignInPath,
    signUpUrl: environment.clerkSignUpPath,
  };
}
