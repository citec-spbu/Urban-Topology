import { ComponentFixture, TestBed } from '@angular/core/testing';

import { OsmnxComponent } from './osmnx.component';

describe('OsmnxComponent', () => {
  let component: OsmnxComponent;
  let fixture: ComponentFixture<OsmnxComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ OsmnxComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(OsmnxComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
