/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  corePlugins: {
    preflight: false,  // 关闭 preflight，避免与 Element Plus 冲突
  },
  theme: {
    extend: {
      colors: {
        primary: '#3b82f6',
        'primary-hover': '#2563eb',
        'bg-sidebar': '#f8fafc',
        'bg-chat': '#ffffff',
        'bg-user-bubble': '#3b82f6',
        'bg-ai-bubble': '#f1f5f9',
        'text-primary': '#1e293b',
        'text-secondary': '#64748b',
        'border-color': '#e2e8f0',
      },
    },
  },
  plugins: [],
}
