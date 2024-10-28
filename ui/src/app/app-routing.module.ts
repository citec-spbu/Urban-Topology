import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { CityListComponent } from './city-list/city-list.component';
import { TownComponent } from './town/town.component';

const routes: Routes = [
  {path:'', redirectTo: '/towns', pathMatch: 'full'},
  {path: 'towns', component: CityListComponent},
  {path: 'town/:id', component: TownComponent},
  {path: '**', redirectTo: '/towns'}
];

@NgModule({
  imports: [RouterModule.forRoot(routes, { scrollPositionRestoration: 'top' }),],
  exports: [RouterModule]
})
export class AppRoutingModule { }
