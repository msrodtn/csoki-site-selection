/// <reference types="vite/client" />

declare module '@mapbox/mapbox-gl-draw' {
  import type { IControl } from 'mapbox-gl';

  interface DrawOptions {
    displayControlsDefault?: boolean;
    controls?: Record<string, boolean>;
    defaultMode?: string;
    styles?: unknown[];
  }

  class MapboxDraw implements IControl {
    constructor(options?: DrawOptions);
    onAdd(map: mapboxgl.Map): HTMLElement;
    onRemove(map: mapboxgl.Map): void;
    changeMode(mode: string, options?: Record<string, unknown>): void;
    deleteAll(): this;
    getAll(): GeoJSON.FeatureCollection;
    add(geojson: GeoJSON.Feature | GeoJSON.FeatureCollection): string[];
    delete(ids: string | string[]): this;
    getMode(): string;
  }

  export default MapboxDraw;
}

declare module '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_MAPBOX_TOKEN: string;
  readonly VITE_MAPBOX_ACCESS_TOKEN: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
