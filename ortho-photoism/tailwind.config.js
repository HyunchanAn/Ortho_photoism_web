/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            colors: {
                background: "var(--background)",
                foreground: "var(--foreground)",
                primary: {
                    DEFAULT: "#0F172A", // Slate 900
                    foreground: "#F8FAFC", // Slate 50
                },
                secondary: {
                    DEFAULT: "#334155", // Slate 700
                    foreground: "#F8FAFC",
                },
                accent: {
                    DEFAULT: "#0EA5E9", // Sky 500
                    foreground: "#FFFFFF",
                },
                muted: {
                    DEFAULT: "#1E293B", // Slate 800
                    foreground: "#94A3B8", // Slate 400
                },
                border: "var(--border)",
            },
        },
    },
    plugins: [],
};
