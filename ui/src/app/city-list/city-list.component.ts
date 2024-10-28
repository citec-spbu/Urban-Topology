import { Component, OnInit } from '@angular/core';
import { FormControl } from '@angular/forms'; //для использования нужно в app.modules импортировать FormsModule и ReactiveFormsModule
import { BehaviorSubject} from 'rxjs';
import { Town} from '../interfaces/town';
import { TownService } from '../services/town.service';

@Component({
  selector: 'app-city-list',
  templateUrl: './city-list.component.html',
  styleUrls: ['./city-list.component.css']
})
export class CityListComponent implements OnInit {
  page = 0;
  per_page = 1000;
  noMoreCities = false;

  towns: Town[] = [];
  filtredTowns = new BehaviorSubject<Town[]>([]); //BehaviorSubject как observe но можем вручную менять значения, хранит текущее значение
  search = new FormControl('');
  
  constructor(
    private townService: TownService
  ) { 
    this.search.valueChanges.subscribe(val => {
      const value = val;
      if(!value) {this.filtredTowns.next(this.towns); return;} //меняем текушее значение как this.filtredTowns.next(this.towns)
      const f = this.towns.filter(t => t.city_name.toLowerCase().includes(val.toLowerCase())) //список городов, содержащих подстрооку val
      this.filtredTowns.next(f);
    })
  }

  ngOnInit(): void {
    this.townService.getTowns(this.page, this.per_page).subscribe(towns => {
      this.towns = towns;
      this.filtredTowns.next(towns);
    });
  }

  getImage(longitude: number, latitude: number): string{
    const zoom = 10;

    return `http://static-maps.yandex.ru/1.x/?lang=en-US&ll=${longitude},${latitude}&size=450,450&z=${zoom}&l=map`
  }

  onLoadMore(){
    this.townService.getTowns(this.page + 1, this.per_page).subscribe(res => {
      this.page += 1;
      if(res.length < this.per_page) this.noMoreCities = true;
      this.towns.push(...res);
      this.search.reset();
      // this.filtredTowns.next(this.towns);
    })
  }
}