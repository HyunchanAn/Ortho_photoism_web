'use client';

import React, { useEffect, useRef } from 'react';
import { Canvas } from 'fabric'; // Fabric v6
import { CanvasConfig } from '@/types/template';
import { useEditorStore } from '@/store/editorStore';

interface PhotoSlotProps {
    config: CanvasConfig;
}

export default function PhotoSlot({ config }: PhotoSlotProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const fabricRef = useRef<Canvas | null>(null);
    // We might store this instance in the global store later

    // Store actions
    const setEditingCanvasId = useEditorStore((s) => s.setEditingCanvasId);

    const handleContextMenu = (e: React.MouseEvent) => {
        e.preventDefault();
        setEditingCanvasId(config.id);
    };

    useEffect(() => {
        if (!canvasRef.current) return;

        // Initialize Fabric Canvas
        // V6 might throw if canvas is already initialized or if ref is null
        const canvas = new Canvas(canvasRef.current, {
            width: canvasRef.current.parentElement?.clientWidth || 300,
            height: canvasRef.current.parentElement?.clientHeight || 300,
            backgroundColor: config.background || '#111',
            selection: true, // Multi-selection inside a canvas
        });

        fabricRef.current = canvas;

        // Register to store
        useEditorStore.getState().registerCanvas(config.id, canvas);
        console.log(`Canvas initialized: ${config.id}`);

        // Cleanup
        return () => {
            useEditorStore.getState().unregisterCanvas(config.id);
            canvas.dispose();
            fabricRef.current = null;
        };
    }, [config]);

    const handleReset = () => {
        if (fabricRef.current) {
            fabricRef.current.clear();
            fabricRef.current.backgroundColor = config.background || '#111';
            fabricRef.current.requestRenderAll();
            // Also notify store to clear file association if needed
        }
    };

    const handleResetPosition = () => {
        const canvas = fabricRef.current;
        if (!canvas) return;

        const objects = canvas.getObjects();
        // Assuming the first object is the main photo
        const img = objects[0];
        if (img) {
            const canvasWidth = canvas.width || 300;
            const canvasHeight = canvas.height || 300;

            // Reset to center, 0 rotation, but keep scale? Or reset scale to "fit"?
            // Spec says "reset position and angle... maintaining other adjustments".
            img.set({
                left: canvasWidth / 2,
                top: canvasHeight / 2,
                angle: 0,
                originX: 'center',
                originY: 'center'
                // scaleX, scaleY maintained? "maintaining any other adjustments"
            });
            img.setCoords();
            canvas.requestRenderAll();
        }
    };

    // Handle Resize Observer to update fabric dimension? 
    // For now, simplify.

    // Select state
    const isSelected = useEditorStore((s) => s.selectedSlotIds.includes(config.id));
    const toggleSelect = useEditorStore((s) => s.toggleSlotSelection);
    const mirrorImage = useEditorStore((s) => s.mirrorImage);

    return (
        <div
            className={`w-full h-full relative border-2 transition-colors group ${isSelected ? 'border-accent' : 'border-transparent hover:border-accent/50'}`}
            onClick={() => toggleSelect(config.id, true)}
            onContextMenu={handleContextMenu}
        >
            <canvas ref={canvasRef} className="w-full h-full block" />

            {/* Title Overlay */}
            <div className="absolute top-0 left-0 p-1 pointer-events-none z-10 flex gap-1 items-center">
                <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={(e) => { e.stopPropagation(); toggleSelect(config.id, true); }}
                    className="pointer-events-auto w-3 h-3 accent-accent cursor-pointer"
                />
                <span className="text-[10px] text-white/50 bg-black/50 px-1 rounded">
                    {config.meta.title}
                </span>
            </div>

            {/* Toolbar Overlay (Visible on Hover) */}
            <div className="absolute top-1 right-1 flex space-x-1 opacity-0 group-hover:opacity-100 transition-opacity z-20 items-center bg-black/50 p-1 rounded">
                {/* Rotation Slider */}
                <div className="flex items-center space-x-1 mr-2 border-r border-white/20 pr-2">
                    <span className="text-[8px] text-white">R</span>
                    <input
                        type="range"
                        min="-180"
                        max="180"
                        defaultValue="0"
                        className="w-16 h-1 accent-accent cursor-pointer"
                        onInput={(e) => {
                            e.stopPropagation();
                            const val = parseInt(e.currentTarget.value);
                            useEditorStore.getState().rotateImage(config.id, val);
                        }}
                        onClick={(e) => e.stopPropagation()}
                    />
                </div>

                <button onClick={(e) => { e.stopPropagation(); mirrorImage(config.id); }} className="p-1 bg-gray-800/80 rounded hover:bg-accent text-white" title="Flip Horizontal">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m16 3-4 4-4-4" /><path d="M12 7v9" /><path d="m16 21-4-4-4 4" /><path d="M4 11h16" /></svg>
                </button>
                <button onClick={handleResetPosition} className="p-1 bg-gray-800/80 rounded hover:bg-accent text-white" title="Reset Position">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74-2.74L3 12" /></svg>
                </button>
                <button onClick={handleReset} className="p-1 bg-gray-800/80 rounded hover:bg-destructive text-white" title="Reset Canvas">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /></svg>
                </button>
            </div>
        </div>
    );
}
