declare module 'svgcanvas'{
    class ImageUtils{
        svg2canvas(svgDataURL: string, width: number, height: number): HTMLCanvasElement
        toDataURL(svgNode: any, width: any, height: any, type: any, encoderOptions: any, options: any): string    
        getImageData(svgNode: any, width: any, height: any, sx: any, sy: any, sw: any, sh: any, options: any): any
    }

    const utils: ImageUtils;

    function SVGCanvasElement(options: any): void;
    const Context: any;
    const Element: typeof SVGCanvasElement;
}
