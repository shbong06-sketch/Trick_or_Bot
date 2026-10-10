# 지도
실제 지도 YAML과 대응하는 이미지 파일을 보관하는 폴더입니다.
기존 backend/maps의 지도는 현재 위치에 유지합니다.
ROS와 웹의 지도 경로를 연결할 때 공통 원본 위치를 정합니다.
빈 PGM 파일을 지도 대신 만들지 않습니다.

## 보관 중인 지도 (2026-10-10 복제)
- `holloween_boo.{yaml,pgm}`: 술래(Boo)용, `holloween_pumpkin.{yaml,pgm}`: 도망자(Pumpkin)용.
- `backend/maps/`의 같은 이름 파일을 **그대로 복제**한 것이다. 원본은 `backend/maps/`(웹이 읽음)이고, 바뀌면 이 폴더도 같이 갱신한다.
- 같은지 확인: `diff -r backend/maps/holloween_boo.yaml ros2_ws/src/tob_bringup/maps/holloween_boo.yaml` (네 파일 모두 출력이 없어야 한다)
- 옛 지도(`past_map/`)는 복제하지 않는다.
