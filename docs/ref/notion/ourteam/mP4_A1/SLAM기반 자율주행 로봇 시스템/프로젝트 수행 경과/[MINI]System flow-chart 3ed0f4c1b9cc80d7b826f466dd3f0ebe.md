# [MINI]System flow-chart

관련 이슈·To-do: [MINI]flow-chart (../%EC%9D%B4%EC%8A%88%20&%20To-do%20%ED%8A%B8%EB%9E%98%EC%BB%A4/%5BMINI%5Dflow-chart%203ed0f4c1b9cc800cb6dde47f680d8fa7.md)
날짜: 2026년 10월 2일
기록일: 2026년 10월 2일
담당자: 봉승현, 민서 김, sj b, 09180_이원호
마지막 수정: 2026년 10월 7일 오전 10:42
분류: 설계 결정
분야: Docs
생성일: 2026년 10월 2일 오전 9:15
작성 상태: 작성 중

## 미니프로젝트

> Detection과 AMR 제어 기술을 배워보고 솔루션에 어떻게 활용할 것인지 선택하고 확인한다.
> 

![image.png](%5BMINI%5DSystem%20flow-chart/image.png)

## 요구사항

1. 만들어진 환경에서 web cam으로 RC car를 detection을 한다.
2. RC Car가 보이면 로봇이 Docking station에서 출발한다.
3. RC car의 근처로 주행한다. - RC Car의 위치는 로봇 시점에서는 보이지 않는 위치
    1. 장애물을 회피하면서 자동으로 주행해야 한다.
4. 인근에 도착한 뒤, AMR Cam을 사용하여 RC Car를 찾는다.
5. 그리고, RC Car 방향으로 접근한다.
    1. 충돌 금지
    2. detection 가능 한계 위치까지 이동
6. RC Car가 이동하면 로봇이 따라간다.

---

**해당 시나리오를 flow chart로 그려본다.**

draw.io를 사용해 여러 기호를 사용한다.

## 추가 요구사항

## Vision 검증 모델

### YOLO OBJ,DET vs YOLO TRACKING

- yolo tracking : 같은 class 내에서도 구분되는 id가 생기고, 계속 추적한다. (화면 내에 있는 경우)
- YOLO 이외의 detection model 검토해볼 것. 솔루션에 따라 최적화 할 것.
- Target과 Dummy 학습
    - 동일한 RC Car 중에 어느 것이 내 RC Car인지?

---

## Flow Chart 수정 사항 기록

### V1

![image.png](%5BMINI%5DSystem%20flow-chart/image%201.png)

### V1-2

![image.png](%5BMINI%5DSystem%20flow-chart/image%202.png)

### V2

- 웹캠: 5프레임 중 3프레임 알림 안정화, Center Crop·conf 0.8 등 세부 사양 추가
- AMR: 초기 위치를 도킹 상태에서 설정, Depth + TF 거리 측정 단계 추가
- 웹캠 PC ↔ AMR PC 토픽(`/webcam/car_alert`, `/webcam/car_pose`) 표시
- 주황 점선 = 확정·연결 필요 항목 (car_pose 연결, AMR 카메라·모델, 정지 거리, 타임아웃)

![image.png](%5BMINI%5DSystem%20flow-chart/image%203.png)