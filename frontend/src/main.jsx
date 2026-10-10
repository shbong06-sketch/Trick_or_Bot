import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import QuarterDemo from './game/QuarterDemo.jsx';
import './styles.css';

// 주소에 ?demo가 있으면 3D 쿼터뷰 확인 화면, 없으면 원래 게임
const demo = new URLSearchParams(location.search).has('demo')

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {demo ? <QuarterDemo /> : <App />}
  </React.StrictMode>
);
