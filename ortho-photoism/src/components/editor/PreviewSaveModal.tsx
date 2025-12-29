'use client';

import React, { useState } from 'react';
import { useEditorStore } from '@/store/editorStore';
import jsPDF from 'jspdf';
import JSZip from 'jszip';
import { saveAs } from 'file-saver';

export default function PreviewSaveModal() {
    const { activeTemplate, canvases, isExportModalOpen, setExportModalOpen } = useEditorStore();
    const [namingPattern, setNamingPattern] = useState('[<Savename>]_<Index>');

    if (!isExportModalOpen) return null;

    // Generate preview list
    const previewItems = activeTemplate.canvases.map((config, index) => {
        // Logic to generate name
        let name = namingPattern
            .replace('<Savename>', config.meta.savename || config.id)
            .replace('<Title>', config.meta.title)
            .replace('<Index>', (index + 1).toString().padStart(2, '0'));

        // Remove brackets if user used them for grouping visually but logic is replace
        name = name.replace('[', '').replace(']', '');

        const hasImage = !!canvases[config.id];
        return { ...config, generatedName: name, hasImage };
    });

    const handleBatchSave = async () => {
        try {
            console.log('Starting Batch Save...');
            const zip = new JSZip();

            for (const item of previewItems) {
                if (item.hasImage) {
                    try {
                        const canvas = canvases[item.id];
                        console.log(`Processing ${item.id} for Zip...`);
                        const dataURL = canvas.toDataURL({ format: 'jpeg', quality: 0.9, multiplier: 2 });
                        const base64 = dataURL.split(',')[1];
                        zip.file(`${item.generatedName}.jpg`, base64, { base64: true });
                    } catch (innerErr) {
                        console.error(`Error processing item ${item.id} for zip`, innerErr);
                    }
                }
            }

            console.log('Generating Zip...');
            const blob = await zip.generateAsync({ type: 'blob' });
            console.log(`Zip generated. Size: ${blob.size}`);

            saveAs(blob, 'ortho_photos.zip');
            console.log('Zip Download Triggered via FileSaver');
        } catch (e) {
            console.error('Batch Save Failed:', e);
            alert('Batch Save Failed. Check console.');
        }
    };

    const handlePDFExport = async () => {
        try {
            console.log('Starting PDF Export...');
            // Basic PDF Export using jspdf
            // Capture the grid? Or compose page?
            // Composing is better for strict layout (A4).
            // We will place images based on their relative geometry on an A4 page.

            const doc = new jsPDF({
                orientation: 'landscape',
                unit: 'mm',
                format: 'a4'
            });

            const pageWidth = 297;
            const pageHeight = 210;
            const margin = 10;
            const contentWidth = pageWidth - (margin * 2);
            const contentHeight = pageHeight - (margin * 2);

            // We assume the template is square-ish or fits in landscape.
            // We map template geometry (0-1) to content area.

            // Need async wait for loading images? No, dataURLs are synchronous from fabric if images loaded.

            for (const item of previewItems) {
                if (item.hasImage) {
                    try {
                        console.log(`Processing ${item.id} for PDF...`);
                        const canvas = canvases[item.id];
                        // Force multiplier 1 to avoid memory limits or taint issues during debug
                        const dataURL = canvas.toDataURL({ format: 'jpeg', quality: 0.8, multiplier: 1 });

                        console.log(`Got dataURL for ${item.id}, length: ${dataURL.length}`);

                        const x = margin + (item.geometry.left * contentWidth);
                        const y = margin + (item.geometry.top * contentHeight);
                        const w = item.geometry.width * contentWidth;
                        const h = item.geometry.height * contentHeight;

                        // Add white border/gap? Fabric grid handles it.
                        // Directly add image
                        doc.addImage(dataURL, 'JPEG', x + 1, y + 1, w - 2, h - 2); // padding

                        // Add Title Text below?
                        doc.setFontSize(8);
                        doc.text(item.meta.title, x + 2, y + h - 2);
                    } catch (innerErr) {
                        console.error(`Error processing item ${item.id}`, innerErr);
                    }
                }
            }

            // Add Hospital Logo / Patient Name placeholder
            doc.setFontSize(14);
            doc.text("Patient: ____________________", margin, margin - 2);
            doc.setFontSize(10);
            doc.text(new Date().toLocaleDateString(), pageWidth - margin - 30, margin - 2);

            console.log('Generating PDF Blob...');
            const pdfBlob = doc.output('blob');
            saveAs(pdfBlob, 'ortho_report.pdf');
            console.log('PDF Saved via FileSaver!');
        } catch (e) {
            console.error('PDF Export Failed:', e);
            alert('PDF Export Failed. Check console for details.');
        }
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm" onClick={() => setExportModalOpen(false)}>
            <div className="bg-slate-900 border border-slate-700 p-6 rounded-lg w-[800px] h-[600px] flex flex-col shadow-2xl" onClick={e => e.stopPropagation()}>
                <h2 className="text-xl font-bold mb-4 text-white">Export & Save</h2>

                {/* Renamer Section */}
                <div className="mb-6 p-4 bg-slate-800 rounded border border-slate-700">
                    <label className="block text-sm text-slate-400 mb-2">Renamer Pattern</label>
                    <div className="flex gap-2">
                        <input
                            className="flex-1 bg-slate-950 border border-slate-600 rounded px-3 py-2 text-white font-mono text-sm"
                            value={namingPattern}
                            onChange={e => setNamingPattern(e.target.value)}
                        />
                        <button className="px-3 py-2 bg-slate-700 rounded hover:bg-slate-600 text-xs">Reset</button>
                    </div>
                    <p className="text-xs text-slate-500 mt-2">Available Tags: &lt;Savename&gt;, &lt;Title&gt;, &lt;Index&gt;</p>
                </div>

                {/* Preview List */}
                <div className="flex-1 overflow-auto border border-slate-800 rounded bg-slate-950/50 p-2">
                    <table className="w-full text-sm text-left">
                        <thead className="text-slate-500 border-b border-slate-800">
                            <tr>
                                <th className="p-2">Slot</th>
                                <th className="p-2">Status</th>
                                <th className="p-2">Output Filename</th>
                            </tr>
                        </thead>
                        <tbody>
                            {previewItems.map(item => (
                                <tr key={item.id} className="border-b border-slate-800/50 hover:bg-white/5">
                                    <td className="p-2 text-slate-300">{item.meta.title}</td>
                                    <td className="p-2">
                                        {item.hasImage ? <span className="text-green-500">Ready</span> : <span className="text-red-500">Empty</span>}
                                    </td>
                                    <td className="p-2 font-mono text-accent">{item.generatedName}.jpg</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Actions */}
                <div className="mt-6 flex justify-end gap-3 pt-4 border-t border-slate-700">
                    <button className="px-4 py-2 rounded text-slate-300 hover:text-white" onClick={() => setExportModalOpen(false)}>
                        Cancel
                    </button>
                    <button className="px-4 py-2 rounded bg-purple-600 text-white hover:bg-purple-500 font-medium" onClick={handlePDFExport}>
                        Export PDF Route
                    </button>
                    <button className="px-4 py-2 rounded bg-accent text-accent-foreground hover:bg-sky-400 font-bold" onClick={handleBatchSave}>
                        Download All (ZIP)
                    </button>
                </div>
            </div>
        </div>
    );
}
