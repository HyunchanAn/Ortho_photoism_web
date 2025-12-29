'use client';

import React, { useState, useEffect } from 'react';
import { useEditorStore } from '@/store/editorStore';

export default function PropertiesModal() {
    const { activeTemplate, editingCanvasId, setEditingCanvasId, updateCanvasConfig } = useEditorStore();
    const [formData, setFormData] = useState<any>(null);

    const targetCanvas = activeTemplate.canvases.find(c => c.id === editingCanvasId);

    useEffect(() => {
        if (targetCanvas) {
            setFormData({
                title: targetCanvas.meta.title,
                description: targetCanvas.meta.description,
                savename: targetCanvas.meta.savename,
                preloadKeywords: targetCanvas.automation.preloadKeywords.join(', '),
                background: targetCanvas.background || '',
            });
        }
    }, [targetCanvas]);

    if (!editingCanvasId || !targetCanvas || !formData) return null;

    const handleSave = () => {
        updateCanvasConfig(editingCanvasId, {
            meta: {
                ...targetCanvas.meta,
                title: formData.title,
                description: formData.description,
                savename: formData.savename
            },
            automation: {
                preloadKeywords: formData.preloadKeywords.split(',').map((s: string) => s.trim()).filter((s: string) => s)
            },
            background: formData.background
        });
        setEditingCanvasId(null);
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setEditingCanvasId(null)}>
            <div className="bg-slate-900 border border-slate-700 p-6 rounded-lg w-96 shadow-xl" onClick={e => e.stopPropagation()}>
                <h2 className="text-lg font-semibold mb-4 text-white">Edit Canvas Properties</h2>

                <div className="space-y-4 text-sm">
                    <div>
                        <label className="block text-slate-400 mb-1">Title</label>
                        <input
                            className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-white focus:border-accent outline-none"
                            value={formData.title}
                            onChange={e => setFormData({ ...formData, title: e.target.value })}
                        />
                    </div>
                    <div>
                        <label className="block text-slate-400 mb-1">Description</label>
                        <input
                            className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-white focus:border-accent outline-none"
                            value={formData.description}
                            onChange={e => setFormData({ ...formData, description: e.target.value })}
                        />
                    </div>
                    <div>
                        <label className="block text-slate-400 mb-1">Keywords (comma separated)</label>
                        <input
                            className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-white focus:border-accent outline-none"
                            value={formData.preloadKeywords}
                            onChange={e => setFormData({ ...formData, preloadKeywords: e.target.value })}
                        />
                    </div>
                    <div>
                        <label className="block text-slate-400 mb-1">Save Filename</label>
                        <input
                            className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-white focus:border-accent outline-none"
                            value={formData.savename}
                            onChange={e => setFormData({ ...formData, savename: e.target.value })}
                        />
                    </div>
                </div>

                <div className="mt-6 flex justify-end gap-2">
                    <button className="px-3 py-1.5 rounded text-slate-300 hover:text-white hover:bg-white/5" onClick={() => setEditingCanvasId(null)}>
                        Cancel
                    </button>
                    <button className="px-3 py-1.5 rounded bg-accent text-accent-foreground hover:bg-sky-400 font-medium" onClick={handleSave}>
                        Save Changes
                    </button>
                </div>
            </div>
        </div>
    );
}
