/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        'brand-purple': '#663399',
        'brand-purple-light': '#593196',
      },
    },
  },
  plugins: [
    require('daisyui'),
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
  daisyui: {
    themes: [
      {
        pneumo: {
          "primary": "#663399",        // 기존 #663399 색상 사용
          "secondary": "#A991D4",      // Bootstrap의 secondary 색상
          "accent": "#593196",         // Bootstrap의 purple 색상
          "neutral": "#3d4451",
          "base-100": "#ffffff",
          "info": "#009CDC",           // Bootstrap의 info 색상
          "success": "#13B955",        // Bootstrap의 success 색상
          "warning": "#EFA31D",        // Bootstrap의 warning 색상
          "error": "#FC3939",          // Bootstrap의 danger 색상
        },
      },
      "light",
      "dark",
    ],
  },
}
