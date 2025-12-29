import { create } from 'zustand';
import { CanvasConfig, TemplateDefinition } from '@/types/template';
import { OrthoBasicTemplate } from '@/data/orthodontic_basic';
import type { Canvas as FabricCanvas } from 'fabric';

interface EditorState {
    activeTemplate: TemplateDefinition;
    files: Record<string, string>; // Filename -> ObjectURL
    canvases: Record<string, FabricCanvas>; // CanvasID -> Fabric Instance
    selectedSlotIds: string[];

    // Actions
    setActiveTemplate: (template: TemplateDefinition) => void;
    registerCanvas: (id: string, canvas: FabricCanvas) => void;
    unregisterCanvas: (id: string) => void;
    addFiles: (newFiles: File[]) => void;
    autoAllocate: () => void;
    toggleSlotSelection: (id: string, multiple?: boolean) => void;
    setSlotSelection: (ids: string[]) => void;

    updateGuideline: (id: string, pos: number) => void;
    mirrorImage: (id: string) => void;
    rotateImage: (id: string, angle: number) => void;

    updateCanvasConfig: (id: string, partialConfig: Partial<CanvasConfig>) => void;
    editingCanvasId: string | null;
    setEditingCanvasId: (id: string | null) => void;

    isExportModalOpen: boolean;
    setExportModalOpen: (isOpen: boolean) => void;
}

export const useEditorStore = create<EditorState>((set, get) => ({
    activeTemplate: OrthoBasicTemplate,
    files: {},
    canvases: {},
    selectedSlotIds: [],
    editingCanvasId: null,
    isExportModalOpen: false,

    setActiveTemplate: (template) => set({ activeTemplate: template }),

    setEditingCanvasId: (id) => set({ editingCanvasId: id }),
    setExportModalOpen: (isOpen) => set({ isExportModalOpen: isOpen }),

    updateCanvasConfig: (id, partialConfig) => {
        set((state) => ({
            activeTemplate: {
                ...state.activeTemplate,
                canvases: state.activeTemplate.canvases.map(c =>
                    c.id === id ? { ...c, ...partialConfig, meta: { ...c.meta, ...(partialConfig.meta || {}) }, automation: { ...c.automation, ...(partialConfig.automation || {}) } } : c
                )
            }
        }));
    },

    updateGuideline: (id, pos) => {
        set((state) => ({
            activeTemplate: {
                ...state.activeTemplate,
                guidelines: state.activeTemplate.guidelines.map(g =>
                    g.id === id ? { ...g, position: pos } : g
                )
            }
        }));
    },

    toggleSlotSelection: (id, multiple = true) => {
        set((state) => {
            const isSelected = state.selectedSlotIds.includes(id);
            if (!multiple) {
                return { selectedSlotIds: isSelected ? [] : [id] }; // Single select mode behavior if needed
            }
            return {
                selectedSlotIds: isSelected
                    ? state.selectedSlotIds.filter(sid => sid !== id)
                    : [...state.selectedSlotIds, id]
            };
        });
    },

    setSlotSelection: (ids) => set({ selectedSlotIds: ids }),

    registerCanvas: (id, canvas) => {
        set((state) => ({ canvases: { ...state.canvases, [id]: canvas } }));
        console.log(`Registered canvas: ${id}`);
    },

    unregisterCanvas: (id) => {
        set((state) => {
            const newCanvases = { ...state.canvases };
            delete newCanvases[id];
            return { canvases: newCanvases };
        });
    },

    addFiles: (newFiles) => {
        const startCount = Object.keys(get().files).length;
        const newFileMap: Record<string, string> = {};

        newFiles.forEach((file) => {
            newFileMap[file.name] = URL.createObjectURL(file);
        });

        set((state) => ({ files: { ...state.files, ...newFileMap } }));

        // Trigger auto-allocation immediately after add (optional, per spec "Smart Uploader")
        get().autoAllocate();
    },

    mirrorImage: (id: string) => {
        const { canvases } = get();
        const canvas = canvases[id];
        if (!canvas) return;

        const img = canvas.getObjects()[0];
        if (img && img.isType('image')) {
            img.set('flipX', !img.flipX);
            canvas.requestRenderAll();
        }
    },

    rotateImage: (id: string, angle: number) => {
        const { canvases } = get();
        const canvas = canvases[id];
        if (!canvas) return;

        const img = canvas.getObjects()[0];
        if (img && img.isType('image')) {
            // Logic to rotate around the canvas center (which is the viewport center)
            const cx = (canvas.width || 0) / 2;
            const cy = (canvas.height || 0) / 2;

            // Fabric util to rotate point
            // We rotate the object's center point around the canvas center point
            // current center
            // We set the absolute angle, so we need to recalculate position from scratch or relative?
            // "Size adjustment" is usually absolute or relative driven by mouse. slider is absolute?
            // Let's implement absolute rotation from the slider (0-360 or +/- 180).
            // But if user panned, we need to respect that offset rotated?

            // Simplified approach: 
            // 1. Store the initial unrotated offset if needed? No, too complex state.
            // 2. Just rotate the object in place? (User rejected "image center")
            // 3. User said "Center of rotation should be block's center".

            // Implementation: Rotate the point (img.left, img.top) around (cx, cy) by the difference in angle?
            // If we use a slider, we get a target Angle.
            // delta = targetAngle - currentAngle.

            const currentAngle = img.angle || 0;
            const delta = angle - currentAngle;

            if (delta === 0) return;

            // Convert to radians
            const rad = (import('fabric').then((f) => f.util.degreesToRadians(delta)));
            // Async issue. We can use simple Math. 
            const radDelta = delta * (Math.PI / 180);

            const cos = Math.cos(radDelta);
            const sin = Math.sin(radDelta);

            // Vector from center to object
            const dx = (img.left || 0) - cx;
            const dy = (img.top || 0) - cy;

            // Rotate vector
            const newDx = dx * cos - dy * sin;
            const newDy = dx * sin + dy * cos;

            img.set({
                left: cx + newDx,
                top: cy + newDy,
                angle: angle
            });

            // Update coords to ensure selection box follows
            img.setCoords();
            canvas.requestRenderAll();
        }
    },

    autoAllocate: async () => {
        const { canvases, activeTemplate, files } = get();
        // Import 'fabric' dynamically or assume 'fabric' features are available on the canvas instance
        // Since we only have the instance, we need the Image class constructor. 
        // We'll trust the component to handle rendering if we pass data, OR we do it here.
        // Doing it here is cleaner for "Central Logic".

        // We need Fabric Image class. Since we can't easily import it here without side-effects or async,
        // let's assume we can use `fabric.Image.fromURL` equivalent if available, or pass it in.
        // Actually, in v6, it is `FabricImage.fromURL`. 
        // We might need to import FabricImage at the top if this file is client-side.
        // BUT this is a store. It might run before fabric is loaded? No, addFiles is user interaction.

        const { FabricImage } = await import('fabric'); // Dynamic import to be safe

        for (const [filename, url] of Object.entries(files)) {
            const nameLower = filename.toLowerCase();

            // Find matching canvas
            const targetCanvasConfig = activeTemplate.canvases.find(c =>
                c.automation.preloadKeywords.some(keyword => nameLower.includes(keyword.toLowerCase()))
            );

            if (targetCanvasConfig) {
                const canvasInstance = canvases[targetCanvasConfig.id];
                if (canvasInstance) {
                    // Clear current content? Per spec, replace.
                    canvasInstance.clear();
                    canvasInstance.backgroundColor = targetCanvasConfig.background || '#111'; // Restore bg

                    try {
                        const img = await (FabricImage as any).fromURL(url);

                        // Apply Pre-actions
                        if (targetCanvasConfig.preAction.rotation) {
                            img.rotate(targetCanvasConfig.preAction.rotation);
                        }
                        if (targetCanvasConfig.preAction.flip === 'horizontal') {
                            img.flipX = true;
                        }
                        if (targetCanvasConfig.preAction.flip === 'vertical') {
                            img.flipY = true;
                        }

                        // Scale to fit (contain)
                        const canvasWidth = canvasInstance.width || 300;
                        const canvasHeight = canvasInstance.height || 300;
                        const scaleX = canvasWidth / img.width!;
                        const scaleY = canvasHeight / img.height!;
                        const scale = Math.min(scaleX, scaleY) * targetCanvasConfig.preAction.magnification; // Apply magnification

                        img.scale(scale);

                        // Center
                        img.set({
                            left: canvasWidth / 2,
                            top: canvasHeight / 2,
                            originX: 'center',
                            originY: 'center'
                        });

                        canvasInstance.add(img);
                        canvasInstance.centerObject(img);
                        canvasInstance.requestRenderAll();
                        console.log(`Allocated ${filename} to ${targetCanvasConfig.id}`);
                    } catch (e) {
                        console.error(`Failed to load image ${filename}`, e);
                    }
                }
            }
        }
    }
}));
