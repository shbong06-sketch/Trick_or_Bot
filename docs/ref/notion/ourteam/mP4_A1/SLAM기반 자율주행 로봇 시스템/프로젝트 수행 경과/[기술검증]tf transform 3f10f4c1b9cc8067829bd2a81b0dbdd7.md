# [기술검증]tf transform

날짜: 2026년 10월 6일
기록일: 2026년 10월 6일
담당자: 민서 김
마지막 수정: 2026년 10월 7일 오전 9:44
분류: 실험
분야: ROS2
생성일: 2026년 10월 6일 오후 6:32
작성 상태: 검토 필요

## 검증 목적과 현재 결론

AMR 카메라에서 선택한 이미지 픽셀에 Depth를 결합해 3차원 점을 구하고, TF로 map 좌표계에 변환한 뒤 Nav2 목표로 연결하는 과정을 검증한다.

**현재 기록에서 확인되는 것은 Depth 값 수신과 map 좌표 출력이다.** 목표 설정과 객체 탐지 연계는 메모·영상으로 남아 있으나, 목표 도착 결과와 좌표 정확도에 대한 정량 검증은 아직 기록되어 있지 않다.

이번 페이지는 AMR에 부착된 OAK-D 카메라를 대상으로 한다. 고정 웹캠의 map 변환은 별도의 카메라 위치·자세 보정이 필요하므로 이 결과와 구분한다.

## 1. 좌표 변환 흐름

### 이미지 픽셀 → 카메라 3차원 점 → map 좌표 → 주행 목표

이미지의 픽셀 (u, v)는 길이 단위의 카메라 좌표가 아니다. 해당 픽셀의 깊이 Z와 카메라 내부 파라미터를 사용해 먼저 3차원 점을 계산한다.

```
X_camera = (u - cx) × Z / fx
Y_camera = (v - cy) × Z / fy
Z_camera = Z

p_map = R_map_from_camera × p_camera + t_map_from_camera
```

위 역투영식은 영상의 왜곡 보정 상태와 내부 파라미터가 서로 일치하는 경우에 적용한다. RGB 픽셀을 사용하면 RGB에 정렬된 Depth인지 확인해야 하며, 단순히 영상 크기가 같다는 것만으로 정렬을 증명할 수 없다.

TF는 프레임 사이의 회전과 이동을 제공한다. 실제 입력 점의 optical frame에서 map까지 연결된 변환을 조회한다. 물리적 중간 프레임의 정확한 연결은 첨부 TF PDF 또는 실행 중 TF 도구로 확인해야 한다.

```
TF 조회 방향:
target_frame = map
source_frame = 실제 3차원 점이 표현된 camera optical frame

토픽 이름: /robot1/tf, /robot1/tf_static
프레임 이름: map, odom, base_link, oakd_*_optical_frame 등
```

토픽 namespace가 /robot1이라고 해서 frame_id에도 자동으로 robot1/이 붙는 것은 아니다. 메시지와 TF에 실제로 기록된 이름을 사용한다.

이미지 취득 시각에 맞는 TF를 적용하는 것이 원칙이다. 최신 TF 조회는 영상 취득 당시와 로봇 자세가 달라질 수 있으므로 이동 중 시험에서는 시각을 특히 확인해야 한다.

## 2. TF 구성 확인

### 확인된 내용

| 구분 | 페이지에서 확인되는 기록 | 해석 |
| --- | --- | --- |
| 동적 TF | odom → base_link, odom → base_footprint | 해당 시각의 로봇 자세 변환을 수신 |
| 정적 TF | base_link → shell_link 및 센서·구조물 변환 | 센서 장착 위치와 방향에 관한 변환을 수신 |
| /robot1/tf 발행자 | amcl, create3_repub, robot_state_publisher: 3개 | 여러 발행자가 존재함. 같은 변환의 중복 발행 여부는 별도 확인 |
| /robot1/tf_static 발행자 | create3_repub, robot_state_publisher: 2개 | 두 발행자 모두 TRANSIENT_LOCAL |
| TF 도식 | frames_2026-10-06_18.45.58.pdf | 원본 첨부 보존. 도식 전체 연결은 별도 확인 필요 |

amcl이 발행자로 보이지만, 본문에 붙여넣은 동적 TF 한 메시지에는 map → odom이 없다. 한 번의 echo에 없다는 이유만으로 변환이 미발행된다고 판단하지 않는다.

### QoS 경고 해석

/robot1/tf는 create3_repub의 TRANSIENT_LOCAL과 다른 발행자의 VOLATILE이 섞여 있다. echo에서 VOLATILE로 내려 연결한다는 경고가 발생했다. 이 경고 자체가 TF 변환 실패를 의미하지는 않는다. 메시지 유실 경고도 별도로 남아 있어, 반복 유실이나 조회 실패가 발생한다면 수신 상태와 TF 시각을 확인한다.

- 동적 TF 원본 — /robot1/tf
    
    ```
    ^C(rokey_venv) hv-01@hv-01:~/ROKEY_mP4_A1/rokey_ws$ ros2 topic echo /robot1/tf --once
    Some, but not all, publishers are offering QoSDurabilityPolicy.TRANSIENT_LOCAL. Falling back to QoSDurabilityPolicy.VOLATILE as it will connect to all publishers
    A message was lost!!!
    	total count change:1
    	total count: 1---
    transforms:
    - header:
        stamp:
          sec: 1791279103
          nanosec: 165785024
        frame_id: odom
      child_frame_id: base_link
      transform:
        translation:
          x: 0.02860664762556553
          y: -0.1798374056816101
          z: 0.06681574881076813
        rotation:
          x: 0.0006161695346236229
          y: -0.0013644342543557286
          z: 0.9996131658554077
          w: 0.02777264080941677
    - header:
        stamp:
          sec: 1791279103
          nanosec: 165785024
        frame_id: odom
      child_frame_id: base_footprint
      transform:
        translation:
          x: 0.02920979401555357
          y: -0.17981348238067874
          z: 0.0
        rotation:
          x: 0.0
          y: 0.0
          z: 0.9996142983436584
          w: 0.02777179144322872
    ---
    ```
    
- 정적 TF 원본 — /robot1/tf_static
    
    ```
      child_frame_id: oakd_right_camera_frame
      transform:
        translation:
          x: 0.0
          y: -0.0375
          z: 0.0
        rotation:
          x: 0.0
          y: 0.0
          z: 0.0
          w: 1.0
    - header:
        stamp:
          sec: 1791276707
          nanosec: 693458627
        frame_id: oakd_right_camera_frame
      child_frame_id: oakd_right_camera_optical_frame
      transform:
        translation:
          x: 0.0
          y: 0.0
          z: 0.0
        rotation:
          x: 0.5
          y: -0.4999999999999999
          z: 0.5
          w: -0.5000000000000001
    - header:
        stamp:
          sec: 1791276707
          nanosec: 693458627
        frame_id: shell_link
      child_frame_id: rear_left_tower_standoff
      transform:
        translation:
          x: -0.07607
          y: 0.09066
          z: 0.14757
        rotation:
          x: 0.0
          y: 0.0
          z: 0.0
          w: 1.0
    - header:
        stamp:
          sec: 1791276707
          nanosec: 693458627
        frame_id: shell_link
      child_frame_id: rear_right_tower_standoff
      transform:
        translation:
          x: -0.07607
          y: -0.09066
          z: 0.14757
        rotation:
          x: 0.0
          y: 0.0
          z: 0.0
          w: 1.0
    - header:
        stamp:
          sec: 1791276707
          nanosec: 693458627
        frame_id: shell_link
      child_frame_id: rplidar_link
      transform:
        translation:
          x: -0.04
          y: 0.0
          z: 0.098715
        rotation:
          x: 0.0
          y: 0.0
          z: 0.7071067811865475
          w: 0.7071067811865476
    - header:
        stamp:
          sec: 1791276707
          nanosec: 693458627
        frame_id: base_link
      child_frame_id: shell_link
      transform:
        translation:
          x: 0.0
          y: 0.0
          z: 0.0942
        rotation:
          x: 0.0
          y: 0.0
          z: 0.0
          w: 1.0
    - header:
        stamp:
          sec: 1791276707
          nanosec: 693458627
        frame_id: shell_link
      child_frame_id: tower_sensor_plate
      transform:
        translation:
          x: 0.0
          y: 0.0
          z: 0.25257
        rotation:
          x: 0.0
          y: 0.0
          z: 0.0
          w: 1.0
    ---
    transforms:
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: cliff_side_left
      transform:
        translation:
          x: 0.069723941385746
          y: 0.1605103462934494
          z: 0.028999999165534973
        rotation:
          x: 0.0
          y: 0.7071067966408575
          z: 0.0
          w: 0.7071067657322372
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: cliff_front_left
      transform:
        translation:
          x: 0.1694290190935135
          y: 0.04380417615175247
          z: 0.028999999165534973
        rotation:
          x: 0.0
          y: 0.7071067966408575
          z: 0.0
          w: 0.7071067657322372
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: cliff_front_right
      transform:
        translation:
          x: 0.1694290190935135
          y: -0.04380417615175247
          z: 0.028999999165534973
        rotation:
          x: 0.0
          y: 0.7071067966408575
          z: 0.0
          w: 0.7071067657322372
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: cliff_side_right
      transform:
        translation:
          x: 0.069723941385746
          y: -0.1605103462934494
          z: 0.028999999165534973
        rotation:
          x: 0.0
          y: 0.7071067966408575
          z: 0.0
          w: 0.7071067657322372
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: bump_left
      transform:
        translation:
          x: 0.08749999850988388
          y: 0.1515544354915619
          z: 0.039000000804662704
        rotation:
          x: 0.0
          y: 0.0
          z: 0.5000000126183913
          w: 0.8660253964992068
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: bump_front_left
      transform:
        translation:
          x: 0.1515544354915619
          y: 0.08749999850988388
          z: 0.039000000804662704
        rotation:
          x: 0.0
          y: 0.0
          z: 0.25881905213951417
          w: 0.9659258244035116
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: bump_front_center
      transform:
        translation:
          x: 0.17499999701976776
          y: 0.0
          z: 0.039000000804662704
        rotation:
          x: 0.0
          y: 0.0
          z: 0.0
          w: 1.0
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: bump_front_right
      transform:
        translation:
          x: 0.1515544354915619
          y: -0.08749999850988388
          z: 0.039000000804662704
        rotation:
          x: 0.0
          y: 0.0
          z: -0.25881905213951417
          w: 0.9659258244035116
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: bump_right
      transform:
        translation:
          x: 0.08749999850988388
          y: -0.1515544354915619
          z: 0.039000000804662704
        rotation:
          x: 0.0
          y: 0.0
          z: -0.5000000126183913
          w: 0.8660253964992068
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: ir_intensity_side_left
      transform:
        translation:
          x: 0.0945528969168663
          y: 0.14725741744041443
          z: 0.052000001072883606
        rotation:
          x: 0.0
          y: 0.0
          z: 0.479425538604203
          w: 0.8775825618903728
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: ir_intensity_left
      transform:
        translation:
          x: 0.14144298434257507
          y: 0.10304795205593109
          z: 0.052000001072883606
        rotation:
          x: 0.0
          y: 0.0
          z: 0.30934103818521125
          w: 0.9509511670398726
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: ir_intensity_front_left
      transform:
        translation:
          x: 0.1653674691915512
          y: 0.05725907161831856
          z: 0.052000001072883606
        rotation:
          x: 0.0
          y: 0.0
          z: 0.1657317753008956
          w: 0.9861708668661904
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: ir_intensity_front_center_left
      transform:
        translation:
          x: 0.17481249570846558
          y: 0.008098957128822803
          z: 0.052000001072883606
        rotation:
          x: 0.0
          y: 0.0
          z: 0.02299797226499384
          w: 0.9997355116588079
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: ir_intensity_front_center_right
      transform:
        translation:
          x: 0.16995327174663544
          y: -0.041723862290382385
          z: 0.052000001072883606
        rotation:
          x: 0.0
          y: 0.0
          z: -0.11971220462599909
          w: 0.9928086361749594
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: ir_intensity_front_right
      transform:
        translation:
          x: 0.1478203535079956
          y: -0.09367039799690247
          z: 0.052000001072883606
        rotation:
          x: 0.0
          y: 0.0
          z: -0.2782772104862426
          w: 0.9605008038122589
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: ir_intensity_right
      transform:
        translation:
          x: 0.08053240180015564
          y: -0.15536901354789734
          z: 0.052000001072883606
        rotation:
          x: 0.0
          y: 0.0
          z: -0.5192729617038252
          w: 0.8546084432319504
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: ir_omni
      transform:
        translation:
          x: 0.17499999701976776
          y: 0.0
          z: 0.09
        rotation:
          x: 0.0
          y: 0.0
          z: 0.0
          w: 1.0
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: mouse
      transform:
        translation:
          x: 0.10040999203920364
          y: 0.08649546653032303
          z: 0.04
        rotation:
          x: 0.0
          y: 0.0
          z: 0.9294452734363258
          w: 0.36896000282804864
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: left_wheel
      transform:
        translation:
          x: 0.0
          y: 0.11649999767541885
          z: 0.035750001668930054
        rotation:
          x: -0.7071067966408575
          y: 0.0
          z: 0.0
          w: 0.7071067657322372
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: right_wheel
      transform:
        translation:
          x: 0.0
          y: -0.11649999767541885
          z: 0.035750001668930054
        rotation:
          x: -0.7071067966408575
          y: 0.0
          z: 0.0
          w: 0.7071067657322372
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: button_1
      transform:
        translation:
          x: 0.05999999865889549
          y: 0.03700000047683716
          z: 0.07999999821186066
        rotation:
          x: 0.0
          y: -0.7071067811865475
          z: 0.0
          w: 0.7071067811865476
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: button_2
      transform:
        translation:
          x: 0.05999999865889549
          y: -0.03700000047683716
          z: 0.07999999821186066
        rotation:
          x: 0.0
          y: -0.7071067811865475
          z: 0.0
          w: 0.7071067811865476
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: button_power
      transform:
        translation:
          x: 0.05999999865889549
          y: 0.0
          z: 0.07999999821186066
        rotation:
          x: 0.0
          y: -0.7071067811865475
          z: 0.0
          w: 0.7071067811865476
    - header:
        stamp:
          sec: 1791276856
          nanosec: 130010549
        frame_id: base_link
      child_frame_id: imu
      transform:
        translation:
          x: 0.050999999046325684
          y: 0.03500000014901161
          z: 0.0685
        rotation:
          x: 0.0
          y: 0.0
          z: 0.0
          w: 1.0
    ---
    ```
    

[frames_2026-10-06_18.45.58.pdf](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5Dtf%20transform/frames_2026-10-06_18.45.58.pdf)

- /robot1/tf 발행자·구독자 및 QoS 원본
    
    ```
    (rokey_venv) hv-01@hv-01:~/ROKEY_mP4_A1/rokey_ws$ ros2 topic info /robot1/tf --verbose
    Type: tf2_msgs/msg/TFMessage
    
    Publisher count: 3
    
    Node name: amcl
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: PUBLISHER
    GID: 01.0f.06.1c.2f.12.23.8e.00.00.00.00.00.00.21.03
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: VOLATILE
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: create3_repub
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: PUBLISHER
    GID: 01.0f.a4.20.e8.04.f9.56.00.00.00.00.00.00.1e.03
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: TRANSIENT_LOCAL
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: robot_state_publisher
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: PUBLISHER
    GID: 01.0f.a4.20.ec.04.32.9f.00.00.00.00.00.00.14.03
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: VOLATILE
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Subscription count: 11
    
    Node name: amcl
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.2f.12.23.8e.00.00.00.00.00.00.1f.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: VOLATILE
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: transform_listener_impl_60f6fb192940
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.89.12.b4.89.00.00.00.00.00.00.3f.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: VOLATILE
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: smoother_server
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.8a.12.58.78.00.00.00.00.00.00.1f.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: VOLATILE
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: transform_listener_impl_609b37f4bda0
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.8b.12.b0.48.00.00.00.00.00.00.3f.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: VOLATILE
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: route_server
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.8c.12.b2.69.00.00.00.00.00.00.1f.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: VOLATILE
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: behavior_server
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.8d.12.97.e4.00.00.00.00.00.00.1f.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: VOLATILE
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: bt_navigator
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.8e.12.17.f2.00.00.00.00.00.00.1f.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: VOLATILE
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: collision_monitor
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.91.12.22.4f.00.00.00.00.00.00.1f.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: VOLATILE
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: docking_server
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.92.12.ba.ca.00.00.00.00.00.00.3a.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: VOLATILE
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: transform_listener_impl_629939178f90
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.ea.14.28.37.00.00.00.00.00.00.4f.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: VOLATILE
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: transform_listener_impl_6299399467f0
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.ea.14.28.37.00.00.00.00.00.00.96.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: VOLATILE
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    ```
    
- /robot1/tf_static 발행자·구독자 및 QoS 원본
    
    ```
    (rokey_venv) hv-01@hv-01:~/ROKEY_mP4_A1/rokey_ws$ ros2 topic info /robot1/tf_static --verbose
    Type: tf2_msgs/msg/TFMessage
    
    Publisher count: 2
    
    Node name: create3_repub
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: PUBLISHER
    GID: 01.0f.a4.20.e8.04.f9.56.00.00.00.00.00.00.20.03
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: TRANSIENT_LOCAL
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: robot_state_publisher
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: PUBLISHER
    GID: 01.0f.a4.20.ec.04.32.9f.00.00.00.00.00.00.15.03
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: TRANSIENT_LOCAL
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Subscription count: 11
    
    Node name: amcl
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.2f.12.23.8e.00.00.00.00.00.00.20.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: TRANSIENT_LOCAL
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: transform_listener_impl_60f6fb192940
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.89.12.b4.89.00.00.00.00.00.00.40.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: TRANSIENT_LOCAL
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: smoother_server
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.8a.12.58.78.00.00.00.00.00.00.20.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: TRANSIENT_LOCAL
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: transform_listener_impl_609b37f4bda0
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.8b.12.b0.48.00.00.00.00.00.00.40.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: TRANSIENT_LOCAL
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: route_server
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.8c.12.b2.69.00.00.00.00.00.00.20.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: TRANSIENT_LOCAL
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: behavior_server
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.8d.12.97.e4.00.00.00.00.00.00.20.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: TRANSIENT_LOCAL
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: bt_navigator
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.8e.12.17.f2.00.00.00.00.00.00.20.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: TRANSIENT_LOCAL
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: collision_monitor
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.91.12.22.4f.00.00.00.00.00.00.20.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: TRANSIENT_LOCAL
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: docking_server
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.92.12.ba.ca.00.00.00.00.00.00.3b.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: TRANSIENT_LOCAL
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: transform_listener_impl_629939178f90
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.ea.14.28.37.00.00.00.00.00.00.50.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: TRANSIENT_LOCAL
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    
    Node name: transform_listener_impl_6299399467f0
    Node namespace: /robot1
    Topic type: tf2_msgs/msg/TFMessage
    Topic type hash: RIHS01_e369d0f05a23ae52508854b66f6aa0437f3449d652e8cbf22d5abe85d020f087
    Endpoint type: SUBSCRIPTION
    GID: 01.0f.06.1c.ea.14.28.37.00.00.00.00.00.00.97.04
    QoS profile:
      Reliability: RELIABLE
      History (Depth): UNKNOWN
      Durability: TRANSIENT_LOCAL
      Lifespan: Infinite
      Deadline: Infinite
      Liveliness: AUTOMATIC
      Liveliness lease duration: Infinite
    ```
    

## 3. Depth 수신과 거리 측정

### 실험 방법

depth_to_map_node에서 클릭한 RGB 픽셀의 Depth를 출력했다. 원본 표기는 1 / 1.5 / 2 m 거리이며, 로그에 출력된 유효 값 전체를 아래 요약에 사용했다. 측정 대상, 거리 기준점, 측정 도구, 필터 설정은 이 페이지에 명시되어 있지 않다.

| 기준 거리 | 출력 로그 수 | 평균 Depth | 범위 | 평균 편차 | 상대 편차 |
| --- | --- | --- | --- | --- | --- |
| 1.00 m | 50 | 1.02362 m | 1.019–1.028 m | +2.362 cm | +2.362% |
| 1.50 m | 39 | 1.52956 m | 1.513–1.547 m | +2.956 cm | +1.971% |
| 2.00 m | 50 | 2.10342 m | 2.087–2.125 m | +10.342 cm | +5.171% |

평균 편차 = 평균 Depth − 표기된 기준 거리. 로그는 소수점 셋째 자리까지 출력되어 계산값은 근사값이다. 출력 로그 수가 독립적인 영상 프레임 수와 같다는 것은 확인되지 않았다.

1 m 시험은 (322, 414)와 (389, 347) 두 클릭 위치가 섞여 있다. 1.5 m는 (389, 297), 2 m는 (349, 321)이다. 따라서 동일 지점에서 거리만 바꾼 비교로 해석하기에는 한계가 있다.

**모든 로그의 valid=True는 유효한 값이 있다는 뜻이며, 실제 거리와 일치한다는 뜻은 아니다.** 2 m 기록에는 약 +10.3 cm의 평균 편차가 남아 있어, map 좌표 오차를 평가할 때 Depth 오차를 함께 고려해야 한다.

- 1.00 m Depth 원본 — 50개 출력
    
    ```
    [INFO] [1791329658.800916581] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.024 m | valid=True
    [INFO] [1791329659.002461228] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.024 m | valid=True
    [INFO] [1791329659.202199776] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.024 m | valid=True
    [INFO] [1791329659.407894821] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.024 m | valid=True
    [INFO] [1791329659.594630326] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.024 m | valid=True
    [INFO] [1791329659.800215190] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.024 m | valid=True
    [INFO] [1791329659.995916012] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.024 m | valid=True
    [INFO] [1791329660.206277155] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.028 m | valid=True
    [INFO] [1791329660.401104879] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.024 m | valid=True
    [INFO] [1791329660.604425022] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.024 m | valid=True
    [INFO] [1791329660.802498243] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.021 m | valid=True
    [INFO] [1791329660.998062920] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.024 m | valid=True
    [INFO] [1791329661.203013376] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.021 m | valid=True
    [INFO] [1791329661.401615852] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.024 m | valid=True
    [INFO] [1791329661.596846342] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.026 m | valid=True
    [INFO] [1791329661.799645404] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.026 m | valid=True
    [INFO] [1791329661.997877190] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.024 m | valid=True
    [INFO] [1791329662.203023973] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.021 m | valid=True
    [INFO] [1791329662.401645953] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.024 m | valid=True
    [INFO] [1791329662.598132088] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.024 m | valid=True
    [INFO] [1791329662.841881721] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.024 m | valid=True
    [INFO] [1791329663.046859756] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.021 m | valid=True
    [INFO] [1791329663.209545101] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.026 m | valid=True
    [INFO] [1791329663.397124648] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.026 m | valid=True
    [INFO] [1791329663.598643097] [robot1.depth_to_map_node]: Depth at pixel (322, 414): 1.024 m | valid=True
    [INFO] [1791329663.696417089] [robot1.depth_to_map_node]: Clicked RGB pixel: (389, 347)
    [INFO] [1791329663.800746898] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.026 m | valid=True
    [INFO] [1791329664.060797899] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.026 m | valid=True
    [INFO] [1791329664.388505975] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.021 m | valid=True
    [INFO] [1791329664.410983151] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.021 m | valid=True
    [INFO] [1791329664.598871552] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.024 m | valid=True
    [INFO] [1791329664.800416857] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.021 m | valid=True
    [INFO] [1791329664.997145363] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.024 m | valid=True
    [INFO] [1791329665.197804751] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.021 m | valid=True
    [INFO] [1791329665.400904591] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.024 m | valid=True
    [INFO] [1791329665.594556628] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.019 m | valid=True
    [INFO] [1791329665.808621380] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.024 m | valid=True
    [INFO] [1791329666.000533134] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.024 m | valid=True
    [INFO] [1791329666.222528919] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.021 m | valid=True
    [INFO] [1791329666.401984897] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.024 m | valid=True
    [INFO] [1791329666.603475654] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.024 m | valid=True
    [INFO] [1791329666.796809259] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.026 m | valid=True
    [INFO] [1791329667.000054596] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.021 m | valid=True
    [INFO] [1791329667.201585513] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.024 m | valid=True
    [INFO] [1791329667.396911555] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.021 m | valid=True
    [INFO] [1791329667.598997030] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.024 m | valid=True
    [INFO] [1791329667.799481607] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.019 m | valid=True
    [INFO] [1791329668.002016257] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.024 m | valid=True
    [INFO] [1791329668.216703218] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.026 m | valid=True
    [INFO] [1791329668.402335973] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.026 m | valid=True
    [INFO] [1791329668.601842482] [robot1.depth_to_map_node]: Depth at pixel (389, 347): 1.026 m | valid=True
    ```
    
- 1.50 m Depth 원본 — 39개 출력
    
    ```
    [INFO] [1791329883.974120012] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.518 m | valid=True
    [INFO] [1791329883.990341780] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.518 m | valid=True
    [INFO] [1791329884.175159224] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.532 m | valid=True
    [INFO] [1791329884.376456574] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.537 m | valid=True
    [INFO] [1791329884.576356675] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.532 m | valid=True
    [INFO] [1791329884.774822345] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.527 m | valid=True
    [INFO] [1791329884.974610089] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.513 m | valid=True
    [INFO] [1791329885.177035415] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.532 m | valid=True
    [INFO] [1791329885.376456070] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.542 m | valid=True
    [INFO] [1791329885.576298871] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.527 m | valid=True
    [INFO] [1791329885.774730008] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.537 m | valid=True
    [INFO] [1791329885.974453368] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.542 m | valid=True
    [INFO] [1791329886.174476584] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.527 m | valid=True
    [INFO] [1791329886.376975790] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.522 m | valid=True
    [INFO] [1791329886.610495756] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.532 m | valid=True
    [INFO] [1791329886.774957788] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.522 m | valid=True
    [INFO] [1791329886.974393049] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.522 m | valid=True
    [INFO] [1791329887.174447604] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.547 m | valid=True
    [INFO] [1791329887.376762687] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.518 m | valid=True
    [INFO] [1791329887.575212229] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.527 m | valid=True
    [INFO] [1791329887.776072653] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.527 m | valid=True
    [INFO] [1791329887.974422372] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.537 m | valid=True
    [INFO] [1791329888.174509377] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.522 m | valid=True
    [INFO] [1791329888.378011717] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.527 m | valid=True
    [INFO] [1791329888.574946552] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.532 m | valid=True
    [INFO] [1791329888.776228583] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.537 m | valid=True
    [INFO] [1791329888.974496934] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.547 m | valid=True
    [INFO] [1791329889.177542577] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.532 m | valid=True
    [INFO] [1791329889.375413735] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.537 m | valid=True
    [INFO] [1791329889.574653253] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.518 m | valid=True
    [INFO] [1791329889.774466781] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.527 m | valid=True
    [INFO] [1791329889.974382735] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.537 m | valid=True
    [INFO] [1791329890.174688316] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.532 m | valid=True
    [INFO] [1791329890.376205972] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.527 m | valid=True
    [INFO] [1791329890.576864712] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.532 m | valid=True
    [INFO] [1791329890.774869285] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.532 m | valid=True
    [INFO] [1791329890.976348079] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.527 m | valid=True
    [INFO] [1791329891.176170852] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.527 m | valid=True
    [INFO] [1791329891.376800486] [robot1.depth_to_map_node]: Depth at pixel (389, 297): 1.522 m | valid=True
    ```
    
- 2.00 m Depth 원본 — 50개 출력
    
    ```
    [INFO] [1791330033.474211880] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330033.671299065] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330033.872060550] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330034.072775263] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.087 m | valid=True
    [INFO] [1791330034.273478257] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330034.472136719] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.125 m | valid=True
    [INFO] [1791330034.672710348] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.087 m | valid=True
    [INFO] [1791330034.873884819] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.087 m | valid=True
    [INFO] [1791330035.071544200] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330035.271397603] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330035.474510163] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330035.672467578] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330035.873560335] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.115 m | valid=True
    [INFO] [1791330036.073291182] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330036.271704531] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.115 m | valid=True
    [INFO] [1791330036.471860723] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.115 m | valid=True
    [INFO] [1791330036.683634397] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330036.871475438] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330037.075053020] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330037.271633318] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330037.471485832] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330037.714810105] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.115 m | valid=True
    [INFO] [1791330037.873611170] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.115 m | valid=True
    [INFO] [1791330038.072116063] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330038.271810054] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330038.473623912] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330038.671565911] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330038.872229515] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330039.072228316] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.115 m | valid=True
    [INFO] [1791330039.274671957] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330039.473933132] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330039.672425677] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330039.871986506] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330040.073225217] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330040.334640440] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.087 m | valid=True
    [INFO] [1791330040.471646339] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330040.673324428] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.115 m | valid=True
    [INFO] [1791330040.871519667] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330041.072512766] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330041.275048121] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.115 m | valid=True
    [INFO] [1791330041.473150330] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.115 m | valid=True
    [INFO] [1791330041.671749985] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330041.871901047] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330042.072363588] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330042.272036373] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330042.473460376] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.115 m | valid=True
    [INFO] [1791330042.674016880] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330042.874646261] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    [INFO] [1791330043.071391260] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.106 m | valid=True
    [INFO] [1791330043.273097955] [robot1.depth_to_map_node]: Depth at pixel (349, 321): 2.097 m | valid=True
    ```
    

## 4. 카메라 점의 map 좌표 변환

### 기록된 입력 조건

| 항목 | 기록값 |
| --- | --- |
| RGB 크기 | 704 × 704, 3채널 |
| Depth 크기 | 704 × 704 |
| fx / fy | 564.65 / 564.65 |
| cx / cy | 353.16 / 355.36 |
| 노드 메시지 | TF Tree stabilized. Starting image display. |

위 조건은 ts 기록에만 명시되어 있다. 내부 파라미터가 실제 사용 영상의 리사이즈·크롭·왜곡 보정과 일치하는지, Depth와 RGB의 시각이 맞는지 추가로 확인한다. “TF Tree stabilized”는 노드의 상태 메시지이며 TF 정확도의 정량 검증 결과는 아니다.

### 원문 기준 위치와 출력 비교

원문에 “실제 위치”로 기록된 값:

```
x = -1.6431350708007812
y = -0.7022634148597717
z =  0.183349609375
```

이 위치의 측정 방법, frame_id, 대상의 기준점이 기록되어 있지 않다. 클릭한 물체 표면 점과 동일한 점인지 확인하기 전에는 참값으로 확정하거나 좌표 오차를 계산하지 않는다.

| 원문 표기 | 클릭 위치 | 출력 좌표 범위 (m) | 확인 가능한 내용 |
| --- | --- | --- | --- |
| 측정 위치 - ts X | 해당 블록에 미기록 | x: −1.68~−1.67 / y: −0.64 / z: 0.03 | 37개 map 좌표 출력 |
| 측정 위치 - ts | (479, 403), (493, 414) | x: −1.75~−1.70 / y: −0.54~−0.48 / z: 0.06~0.10 | 37개 map 좌표 출력. 서로 다른 클릭 지점 포함 |

원문 ts는 타임스탬프 관련 비교 표기로 보이지만, 코드가 첨부되어 있지 않아 실제 적용 방법은 확인되지 않는다. 두 기록의 클릭 지점·로봇 자세·영상 취득 조건을 맞췄다는 증거도 없어, ts 적용이 정확도를 개선했다고 결론 내리지 않는다. 출력 범위가 좁아도 일정한 좌표 편차는 존재할 수 있다.

- map 좌표 원본 — ts X
    
    ```
    [INFO] [1791331068.787807687] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331068.992622253] [robot1.depth_to_map_node]: Map coordinate: (-1.68, -0.64, 0.03)
    [INFO] [1791331069.184187317] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331069.400670915] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331069.672700118] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331069.802874359] [robot1.depth_to_map_node]: Map coordinate: (-1.68, -0.64, 0.03)
    [INFO] [1791331070.027179792] [robot1.depth_to_map_node]: Map coordinate: (-1.68, -0.64, 0.03)
    [INFO] [1791331070.195795395] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331070.388433401] [robot1.depth_to_map_node]: Map coordinate: (-1.68, -0.64, 0.03)
    [INFO] [1791331070.698037566] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331070.784226812] [robot1.depth_to_map_node]: Map coordinate: (-1.68, -0.64, 0.03)
    [INFO] [1791331071.007338090] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331071.184004800] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331071.386601942] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331071.585165426] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331071.783853098] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331071.984186754] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331072.184082276] [robot1.depth_to_map_node]: Map coordinate: (-1.68, -0.64, 0.03)
    [INFO] [1791331072.383770778] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331072.583872486] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331072.784590535] [robot1.depth_to_map_node]: Map coordinate: (-1.68, -0.64, 0.03)
    [INFO] [1791331072.984212823] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331073.183826030] [robot1.depth_to_map_node]: Map coordinate: (-1.68, -0.64, 0.03)
    [INFO] [1791331073.384115968] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331073.584353136] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331073.783707284] [robot1.depth_to_map_node]: Map coordinate: (-1.68, -0.64, 0.03)
    [INFO] [1791331073.983677361] [robot1.depth_to_map_node]: Map coordinate: (-1.68, -0.64, 0.03)
    [INFO] [1791331074.195835517] [robot1.depth_to_map_node]: Map coordinate: (-1.68, -0.64, 0.03)
    [INFO] [1791331074.410256535] [robot1.depth_to_map_node]: Map coordinate: (-1.68, -0.64, 0.03)
    [INFO] [1791331074.705421917] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331074.783829324] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331074.984228866] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331075.183963806] [robot1.depth_to_map_node]: Map coordinate: (-1.68, -0.64, 0.03)
    [INFO] [1791331075.413232023] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331075.670453786] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331075.784258098] [robot1.depth_to_map_node]: Map coordinate: (-1.67, -0.64, 0.03)
    [INFO] [1791331075.984445921] [robot1.depth_to_map_node]: Map coordinate: (-1.68, -0.64, 0.03)
    ```
    
- map 좌표 원본 — ts
    
    ```
    [INFO] [1791331174.162851612] [robot1.depth_to_map_node]: Camera intrinsics: fx=564.65, fy=564.65, cx=353.16, cy=355.36
    [INFO] [1791331174.226522880] [robot1.depth_to_map_node]: RGB image shape: (704, 704, 3)
    [INFO] [1791331174.263000140] [robot1.depth_to_map_node]: Depth image shape: (704, 704)
    [INFO] [1791331179.169025155] [robot1.depth_to_map_node]: TF Tree stabilized. Starting image display.
    [INFO] [1791331185.243997295] [robot1.depth_to_map_node]: Clicked pixel: (479, 403)
    [INFO] [1791331185.375245986] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.09)
    [INFO] [1791331185.590186292] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.09)
    [INFO] [1791331185.774386754] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.10)
    [INFO] [1791331185.974812652] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.09)
    [INFO] [1791331186.216659538] [robot1.depth_to_map_node]: Map coordinate: (-1.73, -0.53, 0.09)
    [INFO] [1791331186.376981240] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.09)
    [INFO] [1791331186.573863415] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.09)
    [INFO] [1791331186.804880237] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.10)
    [INFO] [1791331186.975355092] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.09)
    [INFO] [1791331187.212876941] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.09)
    [INFO] [1791331187.397938869] [robot1.depth_to_map_node]: Map coordinate: (-1.73, -0.53, 0.09)
    [INFO] [1791331187.575675146] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.09)
    [INFO] [1791331187.771895355] [robot1.depth_to_map_node]: Map coordinate: (-1.73, -0.53, 0.09)
    [INFO] [1791331188.009775729] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.09)
    [INFO] [1791331188.265862660] [robot1.depth_to_map_node]: Map coordinate: (-1.73, -0.53, 0.09)
    [INFO] [1791331188.397363518] [robot1.depth_to_map_node]: Map coordinate: (-1.73, -0.53, 0.09)
    [INFO] [1791331188.592559462] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.09)
    [INFO] [1791331188.771388105] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.09)
    [INFO] [1791331188.971531625] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.10)
    [INFO] [1791331189.171608882] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.10)
    [INFO] [1791331189.371551015] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.10)
    [INFO] [1791331189.571399146] [robot1.depth_to_map_node]: Map coordinate: (-1.75, -0.54, 0.09)
    [INFO] [1791331189.801681475] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.10)
    [INFO] [1791331189.972811140] [robot1.depth_to_map_node]: Map coordinate: (-1.70, -0.52, 0.10)
    [INFO] [1791331190.172113911] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.53, 0.09)
    [INFO] [1791331190.293761010] [robot1.depth_to_map_node]: Clicked pixel: (493, 414)
    [INFO] [1791331190.374226073] [robot1.depth_to_map_node]: Map coordinate: (-1.73, -0.49, 0.06)
    [INFO] [1791331190.574280341] [robot1.depth_to_map_node]: Map coordinate: (-1.73, -0.48, 0.06)
    [INFO] [1791331190.774404237] [robot1.depth_to_map_node]: Map coordinate: (-1.73, -0.49, 0.06)
    [INFO] [1791331190.995207669] [robot1.depth_to_map_node]: Map coordinate: (-1.72, -0.48, 0.06)
    [INFO] [1791331191.171973429] [robot1.depth_to_map_node]: Map coordinate: (-1.73, -0.49, 0.06)
    [INFO] [1791331191.374815630] [robot1.depth_to_map_node]: Map coordinate: (-1.73, -0.49, 0.06)
    [INFO] [1791331191.574513834] [robot1.depth_to_map_node]: Map coordinate: (-1.73, -0.49, 0.06)
    [INFO] [1791331191.771171428] [robot1.depth_to_map_node]: Map coordinate: (-1.73, -0.48, 0.06)
    [INFO] [1791331191.990667128] [robot1.depth_to_map_node]: Map coordinate: (-1.73, -0.48, 0.06)
    [INFO] [1791331192.177725408] [robot1.depth_to_map_node]: Map coordinate: (-1.73, -0.49, 0.06)
    [INFO] [1791331192.371402339] [robot1.depth_to_map_node]: Map coordinate: (-1.73, -0.49, 0.06)
    [INFO] [1791331192.582042839] [robot1.depth_to_map_node]: Map coordinate: (-1.73, -0.49, 0.06)
    ```
    

## 5. Depth 기반 Nav2 목표 설정

원문 구현 메모: **1차 목표 orientation에 quaternion (x, y, z, w) = (0, 0, 0, 1) 사용.**

이는 회전이 없는 자세이며, map 기준으로 로봇 전방 축을 +X 방향에 맞추는 초기 설정이다. 대상 방향을 바라보는 자세를 계산했다는 의미는 아니다.

현재 기록에는 goal의 frame_id·송신 좌표·Nav2 결과·실제 도착 위치가 없다. 따라서 이 단계는 초기 목표 자세 설정 기록으로 정리한다.

객체 점의 map 좌표와 로봇이 도착할 주행 목표는 구분한다. 후속 구현에서는 객체 앞에 정지할 거리를 반영한 2D 목표 (x, y)와 yaw를 정하고, 객체의 높이 z를 주행 목표에 그대로 넣지 않도록 확인한다.

## 6. 객체 탐지와 주행 목표 연계

객체 탐지와 목표 설정 연계에 관한 시연 영상 3개를 보존했다. 영상별 조건과 성공·실패 결과는 원문에 설명되어 있지 않으며, 이번 정리에서는 영상을 판독해 성공 여부를 확정하지 않았다.

[Screencast from 2026-10-07 09-16-01.webm](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5Dtf%20transform/Screencast_from_2026-10-07_09-16-01.webm)

[Screencast from 2026-10-07 09-18-22.webm](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5Dtf%20transform/Screencast_from_2026-10-07_09-18-22.webm)

[Screencast from 2026-10-07 09-20-08.webm](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5Dtf%20transform/Screencast_from_2026-10-07_09-20-08.webm)

### 시연 기록에 추가할 항목

- 탐지 모델과 대상, 선택한 target_id 또는 bbox 기준점.
- RGB·Depth 시각, source frame, 변환된 객체 map 좌표.
- 객체 앞 정지 거리를 반영한 goal 좌표와 orientation.
- Nav2 결과, 도착 여부, 실제 정지 거리와 반복 성공률.

## 7. 검증 결과와 남은 작업

| 단계 | 현재 기록으로 확인한 범위 | 추가 검증 |
| --- | --- | --- |
| TF 수신 | 동적·정적 변환과 발행자/QoS 출력 | 카메라 optical frame ↔ map 연결 및 시각별 조회 |
| Depth | 1 / 1.5 / 2 m에서 유효값 출력 | 동일 기준점·고정 ROI·독립 프레임으로 오차 재측정 |
| map 좌표 | 클릭 점에 대해 좌표 출력 | 동일한 실제 점의 참값과 비교; 로봇 위치 변경 시 일관성 |
| Nav2 목표 | 초기 quaternion 설정 메모 | goal 송신·action 결과·실제 정지 위치 기록 |
| 탐지 연계 | 시연 영상 3개 첨부 | 탐지→변환→목표→도착의 반복 시험 결과 |

**현 단계의 성과는 Depth와 TF를 활용한 map 좌표 출력까지 실험 기록을 확보한 것이다.** 정확도 검증과 주행 성공 판정은 동일한 기준점·조건으로 결과를 추가 기록한 뒤 판단한다.

## 참고 자료

- [ROS 2 — Writing a listener (Python)](https://docs.ros.org/en/galactic/Tutorials/Intermediate/Tf2/Writing-A-Tf2-Listener-Py.html): target/source 프레임과 최신 시각 조회의 개념 참고. 예제는 Galactic 문서이므로 Jazzy 구현 코드는 설치된 API에 맞춰 확인한다.
- [ROS 2 — Using time (Python)](https://docs.ros.org/en/galactic/Tutorials/Intermediate/Tf2/Learning-About-Tf2-And-Time-Py.html): 시각별 TF 조회와 timeout 개념.