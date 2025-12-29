'use client';

import React from 'react';
import { useEditorStore } from '@/store/editorStore';
import PhotoSlot from './PhotoSlot';
import GuideLayer from './GuideLayer';
import PropertiesModal from './PropertiesModal';
import PreviewSaveModal from './PreviewSaveModal';

export default function EditorLayout() {
    const { activeTemplate, addFiles, files } = useEditorStore();

    const handleDrop = async (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();

        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            const droppedFiles = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
            addFiles(droppedFiles);
        }
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
    };

    return (
        <div
            className="flex h-screen w-full bg-background text-foreground overflow-hidden"
            onDrop={handleDrop}
            onDragOver={handleDragOver}
        >
            <PropertiesModal />
            <PreviewSaveModal />
            {/* Left Panel: Assets */}
            <aside className="w-64 border-r border-border bg-muted/20 p-4 flex flex-col">
                <h2 className="text-sm font-semibold mb-4 uppercase tracking-wider text-muted-foreground">Assets</h2>
                <div className="flex-1 border-2 border-dashed border-border rounded-lg flex items-center justify-center text-muted-foreground text-xs p-4 text-center">
                    Drop Folder Here
                </div>
                {/* Asset List Placeholder */}
                <div className="mt-4 flex-1 overflow-auto">
                    {/* List items will go here */}
                </div>
            </aside>

            {/* Center: Canvas Area */}
            <main className="flex-1 relative bg-slate-950 flex shadow-inner shadow-black">
                {/* We will render the grid of canvases here based on the template */}
                <div className="absolute inset-0 p-8 flex items-center justify-center">
                    <div className="w-full h-full max-w-6xl max-h-[80vh] relative"
                        style={{
                            aspectRatio: '12/13',
                        }}>
                        {/* Guidelines Layer */}
                        <GuideLayer />

                        {activeTemplate.canvases.map((canvas) => (
                            <div key={canvas.id}
                                className="absolute bg-black border border-slate-800 rounded-sm overflow-hidden group"
                                style={{
                                    left: `${canvas.geometry.left * 100}%`,
                                    top: `${canvas.geometry.top * 100}%`,
                                    width: `${(canvas.geometry.width * 100)}%`,
                                    height: `${(canvas.geometry.height * 100)}%`,
                                }}
                            >
                                <PhotoSlot config={canvas} />
                            </div>
                        ))}
                    </div>
                </div>
            </main>

            {/* Right Panel: Tools */}
            <aside className="w-72 border-l border-border bg-muted/20 p-4 flex flex-col">
                <h2 className="text-sm font-semibold mb-4 uppercase tracking-wider text-muted-foreground">Adjustments</h2>
                <div className="text-xs text-muted-foreground mb-2">
                    {/* Show count of selected */}
                    {useEditorStore((s) => s.selectedSlotIds).length} Photo(s) Selected
                </div>

                <div className="space-y-6">
                    <FilterSlider label="Brightness" filterType="Brightness" min={-1} max={1} step={0.05} />
                    <FilterSlider label="Contrast" filterType="Contrast" min={-1} max={1} step={0.05} />
                </div>

                <div className="mt-6 grid grid-cols-2 gap-2">
                    <button className="bg-secondary text-secondary-foreground py-2 px-3 rounded text-xs hover:bg-white/10" onClick={() => applyOneClick('Normalize')}>
                        Normalize
                    </button>
                    <button className="bg-secondary text-secondary-foreground py-2 px-3 rounded text-xs hover:bg-white/10" onClick={() => applyOneClick('Grayscale')}>
                        Grayscale
                    </button>
                </div>

                <div className="mt-auto pt-4 border-t border-border">
                    <button
                        className="w-full bg-accent text-accent-foreground py-2 rounded-md font-medium text-sm hover:bg-sky-400 transition"
                        onClick={() => useEditorStore.getState().setExportModalOpen(true)}
                    >
                        Export / Save
                    </button>
                </div>
            </aside>
        </div>
    );
}

function FilterSlider({ label, filterType, min, max, step }: { label: string, filterType: string, min: number, max: number, step: number }) {
    const { canvases, selectedSlotIds } = useEditorStore();

    const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = parseFloat(e.target.value);
        // In Fabric v6, filters are often exported separately or attached to FabricImage
        // But safe bet is dynamic import of 'filters' namespace if available, or just use `fabric`.
        // We will cast the image object to any or FabricImage to access .filters

        const { FabricImage, filters } = await import('fabric'); // Import filters specifically

        selectedSlotIds.forEach(id => {
            const canvas = canvases[id];
            if (!canvas) return;
            const img = canvas.getObjects()[0]; // Assume first object

            if (img && img.isType('image')) {
                const fabricImg = img as any;

                // Find the filter class
                // filters is an object with keys like Brightness, Contrast etc.
                const FilterClass = (filters as any)[filterType];

                if (FilterClass) {
                    // Remove existing filter of same type
                    if (fabricImg.filters) {
                        fabricImg.filters = fabricImg.filters.filter((f: any) => f.type !== filterType);
                    } else {
                        fabricImg.filters = [];
                    }

                    // Add new
                    if (val !== 0) {
                        fabricImg.filters.push(new FilterClass({ [filterType.toLowerCase()]: val }) as any);
                    }
                    fabricImg.applyFilters();
                    canvas.requestRenderAll();
                }
            }
        });
    };

    return (
        <div className="space-y-2">
            <div className="flex justify-between">
                <label className="text-xs">{label}</label>
            </div>
            <input type="range" min={min} max={max} step={step} defaultValue={0} onChange={handleChange} className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer" />
        </div>
    );
}

const applyOneClick = async (action: string) => {
    const store = useEditorStore.getState();
    const { FabricImage, filters } = await import('fabric');

    store.selectedSlotIds.forEach(id => {
        const canvas = store.canvases[id];
        if (!canvas) return;
        const img = canvas.getObjects()[0];

        if (img && img.isType('image')) {
            const fabricImg = img as any;

            if (!fabricImg.filters) fabricImg.filters = [];

            if (action === 'Grayscale') {
                fabricImg.filters.push(new filters.Grayscale() as any);
                fabricImg.applyFilters();
            }
            if (action === 'Normalize') {
                fabricImg.filters.push(new filters.Contrast({ contrast: 0.1 }) as any);
                fabricImg.filters.push(new filters.Brightness({ brightness: 0.05 }) as any);
                fabricImg.applyFilters();
            }
            canvas.requestRenderAll();
        }
    });
};
