import { Pipe, PipeTransform } from '@angular/core';
import { DomSanitizer, SafeHtml, SafeResourceUrl, SafeScript, SafeStyle, SafeUrl } from '@angular/platform-browser';

@Pipe({
  name: 'safe'
})
export class SafePipe implements PipeTransform {

  constructor(protected _sanitizer: DomSanitizer) { //protected - как private, но извне класса поля и методы видны только классам-настедников
  }

  transform(value?: string, type?: string): SafeHtml | SafeStyle | SafeScript | SafeUrl | SafeResourceUrl | null {
    if(value && type)
      switch (type) {
        case 'html':
          return this._sanitizer.bypassSecurityTrustHtml(value); //bypassSecurityTrustHtml(value)-проверяет доверитильность value. Возвращает safevalue
        case 'style':
          return this._sanitizer.bypassSecurityTrustStyle(value);
        case 'script':
          return this._sanitizer.bypassSecurityTrustScript(value);
        case 'url':
          return this._sanitizer.bypassSecurityTrustUrl(value);
        case 'resourceUrl':
          return this._sanitizer.bypassSecurityTrustResourceUrl(value);
        default:
          return this._sanitizer.bypassSecurityTrustHtml(value);
      }
    else 
      return null;
  }

}
