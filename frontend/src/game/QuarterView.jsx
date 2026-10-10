import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { unpackOcc } from './geometry.js';
import { toWorld, cellToMap, mapBounds, yawToRotY } from './quarterProjection.js';
import './game.css';

export default function QuarterView({ session, pose, boo }) {
  const canvasRef = useRef(null);
  const modelsRef = useRef(null);

  useEffect(() => {
    if (!session) return;
    const canvas = canvasRef.current;

    // 1. 빈 공간, 카메라, 화면에 그려주는 도구, 조명
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0d0b14);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const sun = new THREE.DirectionalLight(0xffffff, 1.0);
    sun.position.set(3, 8, 4);
    scene.add(sun);

    // 2. 지도 → 벽 (테스트용: 벽 칸마다 작은 상자 1개. 나중에 합쳐서 가볍게 만들 예정)
    const m = session.map;
    const occ = unpackOcc(m);
    const wallGeo = new THREE.BoxGeometry(m.res, 0.3, m.res);
    const wallMat = new THREE.MeshStandardMaterial({ color: 0xc8a165 });   // 골판지 색
    for (let r = 0; r < m.h; r++) {
      for (let c = 0; c < m.w; c++) {
        if (!occ[r * m.w + c]) continue;
        const x = m.ox + (c + 0.5) * m.res;
        const y = m.oy + (m.h - r - 0.5) * m.res;
        const wall = new THREE.Mesh(wallGeo, wallMat);
        wall.position.copy(toWorld(x, y, 0.15));
        scene.add(wall);
      }
    }

    // 바닥
    const cx = m.ox + (m.w * m.res) / 2, cy = m.oy + (m.h * m.res) / 2;
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(m.w * m.res, m.h * m.res),
                                 new THREE.MeshStandardMaterial({ color: 0x2a2233 }));
    floor.rotation.x = -Math.PI / 2;
    floor.position.copy(toWorld(cx, cy, 0));
    scene.add(floor);

    // 사탕 = 분홍 공, 탈출문 = 보라 기둥
    for (const cd of session.candies) {
      const candy = new THREE.Mesh(new THREE.SphereGeometry(0.08), new THREE.MeshStandardMaterial({ color: 0xff5fa2 }));
      candy.position.copy(toWorld(cd.x, cd.y, 0.1));
      scene.add(candy);
    }
    const gate = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.4), new THREE.MeshStandardMaterial({ color: 0xa855f7 }));
    gate.position.copy(toWorld(session.gate.x, session.gate.y, 0.2));
    scene.add(gate);
        // 호박·유령 (위치를 받기 전까지는 숨겨둠)
    const pumpkin = createPumpkinModel();
    const booModel = createBooModel();
    pumpkin.visible = false;
    booModel.visible = false;
    scene.add(pumpkin, booModel);
    modelsRef.current = { pumpkin, boo: booModel };

    // 3. 카메라: 지금은 지도 전체를 남쪽 위에서 내려다봄 (확인용)
    const center = toWorld(cx, cy, 0);
    camera.position.set(center.x, 6, center.z + 5);
    camera.lookAt(center);

    // 화면 크기 맞추기 + 매 프레임 그리기
    const resize = () => {
      renderer.setSize(canvas.clientWidth, canvas.clientHeight, false);
      camera.aspect = canvas.clientWidth / canvas.clientHeight;
      camera.updateProjectionMatrix();
    };
    window.addEventListener('resize', resize);
    resize();
    let id;
    const loop = () => { renderer.render(scene, camera); id = requestAnimationFrame(loop); };
    loop();

    // 화면을 떠날 때 정리
    return () => {
      modelsRef.current = null;
      cancelAnimationFrame(id);
      window.removeEventListener('resize', resize);
      scene.traverse((o) => { o.geometry?.dispose(); o.material?.dispose(); });
      renderer.dispose();
    };
  }, [session]);

  useEffect(() => {
    const md = modelsRef.current;
    if (!md) return;
    place(md.pumpkin, pose);
    place(md.boo, boo);
  }, [pose, boo, session]);

  return <canvas ref={canvasRef} className="pr-quarter" />;
}

// 위치 [x, y, yaw]에 모델을 놓는다. 위치를 모르면 숨긴다
function place(model, p) {
  if (!p) { model.visible = false; return; }
  model.position.copy(toWorld(p[0], p[1], 0));
  model.rotation.y = yawToRotY(p[2]);
  model.visible = true;
}

// 로봇 받침 (실제 TurtleBot4 크기 비슷하게, 지름 약 0.34m)
function robotBase() {
  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.17, 0.06, 32),
                              new THREE.MeshStandardMaterial({ color: 0x333333 }));
  base.position.y = 0.03;
  return base;
}

// 얼굴은 +X 쪽에 둔다 (yaw 0 = 지도 오른쪽을 봄)
function createPumpkinModel() {
  const g = new THREE.Group();
  const black = new THREE.MeshBasicMaterial({ color: 0x1a0b00 });
  const body = new THREE.Mesh(new THREE.SphereGeometry(0.13, 32, 20),
                              new THREE.MeshStandardMaterial({ color: 0xff7a00 }));
  body.scale.y = 0.85;                       // 살짝 납작한 호박
  body.position.y = 0.17;
  const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.02, 0.06),
                              new THREE.MeshStandardMaterial({ color: 0x3f6b2a }));
  stem.position.y = 0.30;
  const eyeL = new THREE.Mesh(new THREE.SphereGeometry(0.022), black);
  const eyeR = eyeL.clone();
  eyeL.position.set(0.115, 0.20, 0.045);
  eyeR.position.set(0.115, 0.20, -0.045);
  const mouth = new THREE.Mesh(new THREE.BoxGeometry(0.01, 0.02, 0.08), black);
  mouth.position.set(0.12, 0.14, 0);
  g.add(robotBase(), body, stem, eyeL, eyeR, mouth);
  return g;
}

function createBooModel() {
  const g = new THREE.Group();
  const white = new THREE.MeshStandardMaterial({ color: 0xf4f4ff });
  const black = new THREE.MeshBasicMaterial({ color: 0x111111 });
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.12, 32, 20), white);
  head.position.y = 0.28;
  const body = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.14, 0.2, 32, 1, true), white);
  body.position.y = 0.18;
  const eyeL = new THREE.Mesh(new THREE.SphereGeometry(0.02), black);
  const eyeR = eyeL.clone();
  eyeL.position.set(0.105, 0.30, 0.04);
  eyeR.position.set(0.105, 0.30, -0.04);
  g.add(robotBase(), body, head, eyeL, eyeR);
  return g;
}