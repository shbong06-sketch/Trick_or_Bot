// 지도(ROS map) 좌표 ↔ 3D 쿼터뷰(Three.js) 좌표 변환. 지도·사탕·문·캐릭터가 모두 이 파일만 쓴다.
//   ROS:      바닥 = (x, y), 단위 m, yaw는 반시계 방향 +
//   Three.js: 높이 = Y,  바닥 = (X, Z)  →  (x, y) ↦ (X = x, Z = -y)
import * as THREE from 'three';

// ① 지도 위치(m) → 3D 위치
export function toWorld(x, y, height = 0) {
  return new THREE.Vector3(x, height, -y);
}

// ② 지도 격자 칸(행, 열) → 그 칸 중심의 지도 위치(m). PGM은 0행이 맨 위
export function cellToMap(map, row, col) {
  return [map.ox + (col + 0.5) * map.res, map.oy + (map.h - row - 0.5) * map.res];
}

// ③ 로봇 방향(yaw, 라디안) → 3D 모델 회전값. 모델의 얼굴을 +X 쪽으로 만들면 값이 같다
export function yawToRotY(yaw) {
  return yaw;
}

// ④ 지도 전체의 중심 위치와 크기(m). 바닥 평면 크기, 카메라 기준점에 쓴다
export function mapBounds(map) {
  const width = map.w * map.res, height = map.h * map.res;
  return { cx: map.ox + width / 2, cy: map.oy + height / 2, width, height };
}