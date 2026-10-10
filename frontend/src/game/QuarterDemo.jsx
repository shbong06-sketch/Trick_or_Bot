// 진짜 게임 화면(PlayerPage)을 바로 보기 위한 연습용!! (후에 삭제할 예정)

import React, { useEffect, useState } from 'react';
import QuarterView from './QuarterView.jsx';

// 개발 확인용: 주소에 ?demo가 있을 때 main.jsx가 이 화면을 띄운다.
//   /api/session : 지도·사탕·탈출문 (한 번)
//   /ws/game     : 펌킨·부우 위치 (5 Hz). 듣기만 하고 아무것도 보내지 않는다 → 조작권·로봇에 영향 없음
export default function QuarterDemo() {
  const [session, setSession] = useState(null);
  const [error, setError] = useState(null);
  const [pose, setPose] = useState(null);
  const [boo, setBoo] = useState(null);

  // ① 지도 받기 (한 번)
  useEffect(() => {
    fetch('/api/session?lv=1')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`세션 로드 실패 (${r.status})`))))
      .then(setSession)
      .catch((e) => setError(e.message));
  }, []);

  // ② 위치 받기 (계속)
  useEffect(() => {
    const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/game`);
    ws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.t === 'p') {
        if (m.a) setPose(m.a);
        if (m.b) setBoo(m.b);
      }
    };
    return () => ws.close();
  }, []);

  if (error) return <p style={{ color: '#fff', padding: 16 }}>{error} — 게임 서버(8000)가 켜져 있는지 확인하세요.</p>;
  if (!session) return <p style={{ color: '#fff', padding: 16 }}>지도 불러오는 중…</p>;

  return (
    <div className="pr-screen">
      <QuarterView session={session} pose={pose} boo={boo} />
    </div>
  );
}