import Sigma from "sigma";
import FileSaver from "file-saver";
import * as svg from 'svgcanvas';
/**
 * There is a bug I can't find sources about, that makes it impossible to render
 * WebGL canvases using `#drawImage` as long as they appear onscreen. There are
 * basically two solutions:
 * 1. Use `webGLContext#readPixels`, transform it to an ImageData, put that
 *    ImageData in another canvas, and draw this canvas properly using
 *    `#drawImage`
 * 2. Hide the sigma instance
 * 3. Create a new sigma instance similar to the initial one (dimensions,
 *    settings, graph, camera...), use it and kill it
 * This exemple uses this last solution.
 */


 type SaveTextType = 'application/xml' | 'application/json' | 'image/svg+xml' | 'text/csv';

export function saveText(name: string, text: string, type: SaveTextType) {
  const blob = new Blob([text], {type: `${type};charset=utf-8`});
  FileSaver.saveAs(blob, name);
}
export default async function saveAs( type: 'png' | 'svg', renderer: Sigma, inputLayers?: string[]) {
  const { width, height } = renderer.getDimensions();

  // This pixel ratio is here to deal with retina displays.
  // Indeed, for dimensions W and H, on a retina display, the canvases
  // dimensions actually are 2 * W and 2 * H. Sigma properly deals with it, but
  // we need to readapt here:
  const pixelRatio = window.devicePixelRatio || 1;

  const tmpRoot = document.createElement("DIV");
  tmpRoot.style.width = `${width}px`;
  tmpRoot.style.height = `${height}px`;
  tmpRoot.style.position = "absolute";
  tmpRoot.style.right = "101%";
  tmpRoot.style.bottom = "101%";
  document.body.appendChild(tmpRoot);

  // Instantiate sigma:
  const tmpRenderer = new Sigma(renderer.getGraph(), tmpRoot, renderer.getSettings());

  // Copy camera and force to render now, to avoid having to wait the schedule /
  // debounce frame:
  tmpRenderer.getCamera().setState(renderer.getCamera().getState());
  tmpRenderer.refresh();

  // Create a new canvas, on which the different layers will be drawn:
  const canvas = document.createElement("CANVAS") as HTMLCanvasElement;
  canvas.setAttribute("width", width * pixelRatio + "");
  canvas.setAttribute("height", height * pixelRatio + "");
  
  let ctx: CanvasRenderingContext2D | typeof svg.Context;
  switch (type){
    case 'png': {ctx = canvas.getContext("2d") as CanvasRenderingContext2D; break;}
    case 'svg': {ctx = new svg.Context(width * pixelRatio, height * pixelRatio); break; }
  }

 

  // Draw a white background first:
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, width * pixelRatio, height * pixelRatio);

  // For each layer, draw it on our canvas:
  const canvases = tmpRenderer.getCanvases();
  const layers = inputLayers ? inputLayers.filter((id) => !!canvases[id]) : Object.keys(canvases);
  layers.forEach((id) => {
    ctx.drawImage(
      canvases[id],
      0,
      0,
      width * pixelRatio,
      height * pixelRatio,
      0,
      0,
      width * pixelRatio,
      height * pixelRatio,
    );
  });

  if(type == 'svg') {
    saveText('graph.svg', ctx.getSerializedSvg() , 'image/svg+xml');
    tmpRenderer.kill();
    tmpRoot.remove();
    return;
  }


  // Save the canvas as a PNG image:
  canvas.toBlob((blob) => {
    if (blob) FileSaver.saveAs(blob, "graph.png");
  }, "image/png");
  
  // Cleanup:
  tmpRenderer.kill();
  tmpRoot.remove();
}
