import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ClerkService, ClerkUserButtonComponent } from 'ngx-clerk';

@Component({
  selector: 'app-dashboard',
  imports: [ClerkUserButtonComponent, RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DashboardComponent {
  protected readonly clerk = inject(ClerkService);
}
