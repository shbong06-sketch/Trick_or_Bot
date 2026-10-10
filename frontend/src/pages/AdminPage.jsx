import React from "react";
import Panel from '../components/Panel.jsx';

// 운영자 관제 화면의 정적 레이아웃만 구성합니다. 제어·통신·데이터 저장 기능은 없습니다.
const devices = [
  { name: '술래 AMR', ns: '/robot1' },
  { name: '도망자 AMR', ns: '/robot2' },
  { name: '술래 카메라', ns: 'OAK-D Pro' },
  { name: '도망자 카메라', ns: 'OAK-D Pro' },
  { name: '게임 서버', ns: 'FastAPI' },
  { name: 'CCTV 웹캠', ns: 'USB Webcam' },
];

export default function AdminPage() {
  return (
    <main className="page operator-page">
      <div className="operator-heading">
        <div>
          <span className="operator-kicker">TRICK OR BOT · CONTROL ROOM</span>
          <h1>운영자 관제 화면</h1>
          <p>로봇 상태, 회차 진행, 안전 상황을 확인하는 화면 틀입니다.</p>
        </div>
        <span className="operator-preview">UI 미리보기 · 실제 장비 미연결</span>
      </div>

      <section className="operator-summary" aria-label="회차 요약 자리">
        <div><small>회차 상태</small><strong>대기 중</strong></div>
        <div><small>현재 레벨</small><strong>—</strong></div>
        <div><small>경과 시간</small><strong>--:--</strong></div>
        <div><small>획득 목표</small><strong>— / —</strong></div>
        <div><small>안전 상태</small><strong>확인 전</strong></div>
      </section>

      <div className="operator-grid">
        <div className="operator-main">
          <Panel title="아레나 전체 지도 · 운영자 전용">
            <div className="operator-map-empty">
              <div className="operator-map-center">ARENA MAP<span>지도 · 두 로봇 위치 · 목표 구역 표시 예정</span></div>
              <div className="operator-map-key"><span>● 술래 /robot1</span><span>● 도망자 /robot2</span><span>◇ 목표 위치</span></div>
            </div>
          </Panel>
          <div className="operator-feed-grid">
            <Panel title="술래 카메라 · /robot1"><div className="operator-feed-empty"><span>CAM 01</span><strong>영상 연결 전</strong></div></Panel>
            <Panel title="도망자 카메라 · /robot2"><div className="operator-feed-empty"><span>CAM 02</span><strong>영상 연결 전</strong></div></Panel>
          </div>
          <Panel title="운영 이벤트 기록"><div className="operator-log-empty">회차 진행 및 장애 이벤트가 이 영역에 표시됩니다.</div></Panel>
        </div>

        <aside className="operator-aside">
          <Panel title="장비 연결 현황">
            <div className="operator-devices">
              {devices.map((d) => <div className="operator-device" key={d.name}><div><b>{d.name}</b><small>{d.ns}</small></div><span>미연결</span></div>)}
            </div>
          </Panel>
          <Panel title="술래 AI 상태"><div className="operator-ai-state"><small>상태</small><strong>데이터 없음</strong><small>의심 게이지</small><div className="operator-gauge-empty" /></div></Panel>
          <Panel title="회차 운영"><div className="operator-controls"><button disabled>회차 시작</button><button disabled>일시 정지</button><button disabled>초기화</button><button disabled>수동 조작</button></div><p className="operator-helper">실제 기능을 연결하기 전까지 사용할 수 없습니다.</p></Panel>
          <Panel title="안전 제어"><button className="operator-estop" disabled>⚠ 비상 정지</button><p className="operator-helper">현재는 버튼 모양만 표시합니다. 로봇을 정지시키지 않습니다.</p></Panel>
        </aside>
      </div>
    </main>
  );
}
