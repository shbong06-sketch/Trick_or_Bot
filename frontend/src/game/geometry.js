// 맵 좌표 ↔ 카메라 ↔ 화면 계산과 가림 판정. 서버는 프레임마다 포즈만 보내고 계산은 모두 브라우저에서 한다.

// map 점 p → 광학 프레임 점: R^T (p − t). pose = [x, y, z, qx, qy, qz, qw] (map 기준 카메라 광학 프레임)
export function mapToCamera(pose, p) {
  const [tx, ty, tz, qx, qy, qz, qw] = pose;
  const vx = p[0] - tx, vy = p[1] - ty, vz = p[2] - tz;
  // 켤레 쿼터니언으로 회전: v' = v + 2w(u×v) + 2u×(u×v), u = −(qx,qy,qz)
  const ux = -qx, uy = -qy, uz = -qz;
  const cx1 = uy * vz - uz * vy, cy1 = uz * vx - ux * vz, cz1 = ux * vy - uy * vx;
  const cx2 = uy * cz1 - uz * cy1, cy2 = uz * cx1 - ux * cz1, cz2 = ux * cy1 - uy * cx1;
  return [vx + 2 * (qw * cx1 + cx2), vy + 2 * (qw * cy1 + cy2), vz + 2 * (qw * cz1 + cz2)];
}

// 광학 프레임 점 → 영상 픽셀. 실제 영상 크기가 camera_info와 다르면 내부 파라미터를 비율대로 맞춘다
export function cameraToPixel(cam, frame, pc) {
  const sx = frame.w / cam.w, sy = frame.h / cam.h;
  return [cam.fx * sx * pc[0] / pc[2] + cam.cx * sx, cam.fy * sy * pc[1] / pc[2] + cam.cy * sy];
}

// /api/session의 비트로 묶은 점유 격자(base64) → 셀당 1/0 (0행 = 맵 위쪽)
export function unpackOcc(map) {
  const bits = Uint8Array.from(atob(map.occ), (ch) => ch.charCodeAt(0));
  const out = new Uint8Array(map.w * map.h);
  for (let i = 0; i < out.length; i++) out[i] = (bits[i >> 3] >> (i & 7)) & 1;
  return out;
}

// 두 map 점 사이 직선이 벽 셀을 지나는지. 1/4칸 간격 표본, 양 끝 칸은 제외
export function makeOccluded(map, occ) {
  const cell = (x, y) => {
    const c = Math.floor((x - map.ox) / map.res), r = map.h - 1 - Math.floor((y - map.oy) / map.res);
    return c < 0 || c >= map.w || r < 0 || r >= map.h ? -1 : r * map.w + c;
  };
  return (x0, y0, x1, y1) => {
    const a = cell(x0, y0), b = cell(x1, y1);
    const n = Math.ceil(Math.hypot(x1 - x0, y1 - y0) / (map.res * 0.25));
    for (let i = 1; i < n; i++) {
      const k = cell(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n);
      if (k >= 0 && k !== a && k !== b && occ[k]) return true;
    }
    return false;
  };
}
