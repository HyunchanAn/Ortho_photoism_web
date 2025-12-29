export interface CanvasGeometry {
    width: number; // percentage (0.0 - 1.0) or relative units
    height: number;
    left: number;
    top: number;
}

export interface CanvasPreAction {
    rotation: number; // degrees
    flip: 'horizontal' | 'vertical' | null;
    magnification: number; // scale factor
}

export interface CanvasConfig {
    id: string; // "canvas-1"
    meta: {
        title: string;
        description: string;
        savename: string;
        order: number;
    };
    geometry: CanvasGeometry;
    automation: {
        preloadKeywords: string[];
    };
    preAction: CanvasPreAction;
    background?: string;
    referenceImage?: string; // path to assets
}

export interface GuidelineConfig {
    id: string;
    type: 'global' | 'local';
    orientation: 'horizontal' | 'vertical';
    position: number; // 0.0 to 1.0 (relative to container)
    canvasId?: string; // if local (then position is relative to canvas)
    label?: string;
}

export interface TemplateDefinition {
    id: string;
    title: string;
    description: string;
    author: string;
    version: string;
    canvases: CanvasConfig[];
    guidelines: GuidelineConfig[];
}
