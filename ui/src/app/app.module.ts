import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';

import { AppComponent } from './app.component';
import { AppRoutingModule } from './app-routing.module';
import { CityListComponent } from './city-list/city-list.component';
import { HttpClient, HttpClientModule } from '@angular/common/http';
import { TownComponent } from './town/town.component';
import { ToolbarComponent } from './toolbar/toolbar.component';
import { SafePipe } from './pipes/safe.pipe';
import { LeafletModule } from '@asymmetrik/ngx-leaflet';
import { MapComponent } from './map/map.component';
import { RoadsComponent } from './roads/roads.component'

@NgModule({
  declarations: [
    AppComponent,
    CityListComponent,
    TownComponent,
    ToolbarComponent,
    SafePipe,
    MapComponent,
    RoadsComponent
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    ReactiveFormsModule,
    FormsModule,
    LeafletModule,
    HttpClientModule
  ],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule { }
