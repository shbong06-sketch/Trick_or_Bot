// 진짜 게임 화면(PlayerPage)을 바로 보기 위한 연습용!! (후에 삭제할 예정)

import React, { useEffect, useRef, useState } from 'react';
import QuarterView from './QuarterView.jsx';
import { GameEngine } from './engine.js';

// 개발 확인용 (?demo). 기존 GameEngine이 지도 받기·WASD 전송·위치 받기를 모두 한다.
// ⚠️ 키 입력을 서버로 보내므로 MOCK=1 서버에서만 쓸 것 (실제 로봇에 연결하면 진짜로 움직인다)
export default function QuarterDemo() {
  const videoRef = useRef(null);   // 엔진이 요구하는 영상 canvas (숨김)
  const miniRef = useRef(null);    // 기존 미니맵 (3D와 비교용으로 보여줌)
  const [snap, setSnap] = useState(null);

  useEffect(() => {
    const engine = new GameEngine({ lv: 1, video: videoRef.current, minimap: miniRef.current, onChange: setSnap });
    engine.start();
    return () => engine.destroy();      // 떠날 때 연결 끊기 + 로봇 정지
  }, []);

  return (
    <div className="pr-screen">
      {snap?.session && (
        <QuarterView session={snap.session} pose={snap.pose} boo={snap.boo} />
      )}
      {snap?.error && <p style={{ color: '#fff' }}>{snap.error}</p>}
      <canvas ref={videoRef} style={{ display: 'none' }} />
      <canvas ref={miniRef} className="pr-minimap" />
    </div>
  );
}