'use client';

import React, { useRef, useState } from 'react';
import { useEditorStore } from '@/store/editorStore';
import { GuidelineConfig } from '@/types/template';

export default function GuideLayer() {
    const { activeTemplate, updateGuideline } = useEditorStore();
    const containerRef = useRef<HTMLDivElement>(null);

    // Dragging state
    const [draggingId, setDraggingId] = useState<string | null>(null);

    const handlePointerDown = (e: React.PointerEvent, id: string) => {
        e.preventDefault();
        e.stopPropagation();
        setDraggingId(id);
        (e.target as Element).setPointerCapture(e.pointerId);
    };

    const handlePointerMove = (e: React.PointerEvent) => {
        if (!draggingId || !containerRef.current) return;

        const guideline = activeTemplate.guidelines.find(g => g.id === draggingId);
        if (!guideline) return;

        const rect = containerRef.current.getBoundingClientRect();
        let newPos = 0;

        if (guideline.orientation === 'vertical') {
            newPos = (e.clientX - rect.left) / rect.width;
        } else {
            newPos = (e.clientY - rect.top) / rect.height;
        }

        // Clamp
        newPos = Math.max(0, Math.min(1, newPos));
        updateGuideline(draggingId, newPos);
    };

    const handlePointerUp = (e: React.PointerEvent) => {
        setDraggingId(null);
        (e.target as Element).releasePointerCapture(e.pointerId);
    };

    return (
        <div
            ref={containerRef}
            className="absolute inset-0 pointer-events-none z-50 overflow-hidden" // z-50 to be above everything
            onPointerMove={draggingId ? handlePointerMove : undefined}
            onPointerUp={draggingId ? handlePointerUp : undefined}
        >
            {activeTemplate.guidelines.map(g => (
                <div
                    key={g.id}
                    onPointerDown={(e) => handlePointerDown(e, g.id)}
                    className={`absolute pointer-events-auto cursor-${g.orientation === 'vertical' ? 'col-resize' : 'row-resize'} hover:bg-yellow-400`}
                    style={{
                        // Global guides (Red)
                        backgroundColor: g.type === 'global' ? '#ef4444' : '#3b82f6', // Red-500 or Blue-500
                        opacity: 0.8,
                        ...(g.orientation === 'vertical' ? {
                            top: 0, bottom: 0, width: '2px', left: `${g.position * 100}%`
                        } : {
                            left: 0, right: 0, height: '2px', top: `${g.position * 100}%`
                        })
                    }}
                >
                    {/* Handle touch/grab area enlarged transparently */}
                    <div className={`absolute ${g.orientation === 'vertical' ? '-left-2 -right-2 top-0 bottom-0' : '-top-2 -bottom-2 left-0 right-0'}`} />
                </div>
            ))}
        </div>
    );
}
