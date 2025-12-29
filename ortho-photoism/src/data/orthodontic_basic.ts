import { TemplateDefinition } from "@/types/template";

export const OrthoBasicTemplate: TemplateDefinition = {
    id: "ortho-basic",
    title: "Orthodontic Basic 9",
    description: "Standard 9-photo composite for orthodontic records.",
    author: "PhotoAlign Clone",
    version: "1.0",
    guidelines: [
        { id: "g1", type: "global", orientation: "horizontal", position: 0.5, label: "Global Mid" },
        { id: "g2", type: "global", orientation: "vertical", position: 0.5, label: "Global Center" }
    ],
    canvases: [
        // --- Row 1: Extraoral (Face) (Ratio 3:4 per slot) ---
        // Total Row Height ~ 30.7% of canvas (4 units / 13 units)
        {
            id: "face-rest",
            meta: { title: "Rest", description: "Frontal Rest", savename: "01_frontal_rest", order: 1 },
            geometry: { left: 0, top: 0, width: 0.25, height: 0.307 },
            automation: { preloadKeywords: ["rest", "frontal"] },
            preAction: { rotation: 0, flip: null, magnification: 1 },
            referenceImage: "/assets/ref/face_rest.png"
        },
        {
            id: "face-profile-45", // Was io-overjet
            meta: { title: "Profile 45°", description: "Frontal 45 Profile", savename: "02_profile_45", order: 2 },
            geometry: { left: 0.25, top: 0, width: 0.25, height: 0.307 },
            automation: { preloadKeywords: ["45", "quarter"] },
            preAction: { rotation: 0, flip: null, magnification: 1 },
            referenceImage: "/assets/ref/face_45.png"
        },
        {
            id: "face-profile-90", // Was face-profile
            meta: { title: "Profile 90°", description: "Profile Side", savename: "03_profile_90", order: 3 },
            geometry: { left: 0.5, top: 0, width: 0.25, height: 0.307 },
            automation: { preloadKeywords: ["profile", "side", "90"] },
            preAction: { rotation: 0, flip: null, magnification: 1 },
            referenceImage: "/assets/ref/face_profile.png"
        },
        {
            id: "face-smile",
            meta: { title: "Smile", description: "Frontal Smile", savename: "04_frontal_smile", order: 4 },
            geometry: { left: 0.75, top: 0, width: 0.25, height: 0.307 },
            automation: { preloadKeywords: ["smile", "frontal_smile"] },
            preAction: { rotation: 0, flip: null, magnification: 1 },
            referenceImage: "/assets/ref/face_smile.png"
        },

        // --- Row 2 Area: Intraoral (Cross) (Ratio 4:3 per slot) ---
        // Total Area Height ~ 69.2% (9 units / 13 units)
        // Sub-row height = 0.23 (3 units / 13 units)

        // Top of Cross (Upper)
        {
            id: "io-upper",
            meta: { title: "Upper", description: "Maxillary Occlusal", savename: "05_upper", order: 5 },
            geometry: { left: 0.333, top: 0.307, width: 0.333, height: 0.231 },
            automation: { preloadKeywords: ["upper", "maxillary"] },
            preAction: { rotation: 0, flip: null, magnification: 1 },
            referenceImage: "/assets/ref/io_upper.png"
        },

        // Middle of Cross (Right - Center - Left)
        {
            id: "io-right",
            meta: { title: "Right", description: "Right Buccal", savename: "06_right", order: 6 },
            geometry: { left: 0, top: 0.538, width: 0.333, height: 0.231 },
            automation: { preloadKeywords: ["right", "buccal_right"] },
            preAction: { rotation: 0, flip: null, magnification: 1 }
        },
        {
            id: "io-frontal", // Center
            meta: { title: "Center", description: "Intraoral Frontal", savename: "07_center", order: 7 },
            geometry: { left: 0.333, top: 0.538, width: 0.333, height: 0.231 },
            automation: { preloadKeywords: ["center", "io_front"] },
            preAction: { rotation: 0, flip: null, magnification: 1 }
        },
        {
            id: "io-left",
            meta: { title: "Left", description: "Left Buccal", savename: "08_left", order: 8 },
            geometry: { left: 0.666, top: 0.538, width: 0.333, height: 0.231 },
            automation: { preloadKeywords: ["left", "buccal_left"] },
            preAction: { rotation: 0, flip: null, magnification: 1 }
        },

        // Bottom of Cross (Lower)
        {
            id: "io-lower",
            meta: { title: "Lower", description: "Mandibular Occlusal", savename: "09_lower", order: 9 },
            geometry: { left: 0.333, top: 0.769, width: 0.333, height: 0.231 },
            automation: { preloadKeywords: ["lower", "mandibular"] },
            preAction: { rotation: 0, flip: null, magnification: 1 }
        }
    ]
};
