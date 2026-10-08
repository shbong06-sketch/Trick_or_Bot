# [기술검증]Nav2 parameter test

관련 이슈·To-do: [기술검증]AMR 제어 기술 탐색 및 검증 (../%EC%9D%B4%EC%8A%88%20&%20To-do%20%ED%8A%B8%EB%9E%98%EC%BB%A4/%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DAMR%20%EC%A0%9C%EC%96%B4%20%EA%B8%B0%EC%88%A0%20%ED%83%90%EC%83%89%20%EB%B0%8F%20%EA%B2%80%EC%A6%9D%203ed0f4c1b9cc809e8cabec53f31cb31b.md)
날짜: 2026년 10월 6일
기록일: 2026년 10월 6일
담당자: 봉승현
마지막 수정: 2026년 10월 6일 오후 6:54
분류: 실험
분야: Nav
생성일: 2026년 10월 6일 오후 1:58
작성 상태: 정리 완료

## 1. 실험 목적

Local / Global costmap의 inflation 설정을 변경하면서 장애물 주변 비용 영역과 경로·주행 동작의 차이를 비교하기 위한 기록이다.

현재 기록에는 설정값, RViz 이미지 4장, 기본 설정 영상 1개가 포함되어 있다. 주행 성공률·소요 시간·최소 이격 거리는 별도로 기록되어 있지 않으므로 최적 설정은 아직 확정하지 않는다.

## 2. 변경 파라미터와 의미

| 파라미터 | 의미 | 해석 |
| --- | --- | --- |
| inflation_radius | 장애물 주변에 비용을 부여하는 범위, 단위 m | 값이 클수록 비용 영역이 넓어진다. 장애물과 로봇 사이의 보장된 최소 거리와는 다르다. |
| cost_scaling_factor | 거리 증가에 따른 비용의 지수 감쇠 계수 | 같은 반경·거리에서 값이 클수록 비용이 빠르게 감소한다. 값이 작을수록 높은 비용이 더 멀리 유지된다. |

Local costmap은 로봇 주변의 주행 제어에, Global costmap은 전체 경로 계획에 사용된다. 최종 동작은 footprint와 planner/controller의 비용 평가에도 영향을 받는다.

[공식 자료: Nav2 Jazzy Inflation Layer](https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/costmap_2d/costmap_plugins/inflation/)

## 3. 설정 비교

| 설정 | Local scaling | Local radius (m) | Global scaling | Global radius (m) |
| --- | --- | --- | --- | --- |
| 기본 | 4.0 | 0.45 | 4.0 | 0.45 |
| 1차 | 1.0 | 0.20 | 1.0 | 0.20 |
| 2차 | 4.0 | 0.20 | 1.0 | 0.20 |
| 3차 | 2.0 | 0.60 | 4.0 | 0.80 |

기본 → 1차와 2차 → 3차에서는 여러 변수를 동시에 변경했다. 1차 → 2차는 기록된 inflation 설정 기준으로 Local cost_scaling_factor만 변경하여 비교할 수 있다. 나머지 실행 조건이 동일했는지는 별도 확인이 필요하다.

## 4. 회차별 실험 기록

### 4.1 기본 설정

| Costmap | cost_scaling_factor | inflation_radius (m) |
| --- | --- | --- |
| Local | 4.0 | 0.45 |
| Global | 4.0 | 0.45 |

![image.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DNav2%20parameter%20test/image.png)

[Screencast from 2026-10-06 12-58-48.webm](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DNav2%20parameter%20test/Screencast_from_2026-10-06_12-58-48.webm)

관찰 결과: 이미지·영상 첨부. 별도 주행 판정 및 정량 측정값은 미기록.

- 기본 설정 전체 원문 — nav2.yaml 출력
    
    ```bash
    (rokey_venv) hv-01@hv-01:~/turtlebot4_ws/src/turtlebot4/turtlebot4_navigation/config$ cat nav2.yaml 
    bt_navigator:
      ros__parameters:
        enable_stamped_cmd_vel: true
        global_frame: map
        robot_base_frame: base_link
        odom_topic: odom
        bt_loop_duration: 10
        default_server_timeout: 20
        wait_for_service_timeout: 1000
        action_server_result_timeout: 900.0
        navigators: ["navigate_to_pose", "navigate_through_poses"]
        navigate_to_pose:
          plugin: "nav2_bt_navigator::NavigateToPoseNavigator"
        navigate_through_poses:
          plugin: "nav2_bt_navigator::NavigateThroughPosesNavigator"
        error_code_names:
          - compute_path_error_code
          - follow_path_error_code
    
    controller_server:
      ros__parameters:
        enable_stamped_cmd_vel: true
        controller_frequency: 20.0
        min_x_velocity_threshold: 0.001
        min_y_velocity_threshold: 0.5
        min_theta_velocity_threshold: 0.001
        failure_tolerance: 0.3
        progress_checker_plugins: ["progress_checker"]
        goal_checker_plugins: ["general_goal_checker"]
        controller_plugins: ["FollowPath"]
        use_realtime_priority: false
        progress_checker:
          plugin: "nav2_controller::SimpleProgressChecker"
          required_movement_radius: 0.5
          movement_time_allowance: 10.0
        general_goal_checker:
          stateful: true
          plugin: "nav2_controller::SimpleGoalChecker"
          xy_goal_tolerance: 0.25
          yaw_goal_tolerance: 0.25
        FollowPath:
          plugin: "dwb_core::DWBLocalPlanner"
          debug_trajectory_details: True
          min_vel_x: 0.0
          min_vel_y: 0.0
          max_vel_x: 0.26
          max_vel_y: 0.0
          max_vel_theta: 1.0
          min_speed_xy: 0.0
          max_speed_xy: 0.26
          min_speed_theta: 0.0
          acc_lim_x: 2.5
          acc_lim_y: 0.0
          acc_lim_theta: 3.2
          decel_lim_x: -2.5
          decel_lim_y: 0.0
          decel_lim_theta: -3.2
          vx_samples: 20
          vy_samples: 5
          vtheta_samples: 20
          sim_time: 1.7
          linear_granularity: 0.05
          angular_granularity: 0.025
          xy_goal_tolerance: 0.25
          path_length_tolerance: 1.0
          trans_stopped_velocity: 0.25
          short_circuit_trajectory_evaluation: True
          limit_vel_cmd_in_traj: False
          stateful: True
          critics: ["RotateToGoal", "Oscillation", "BaseObstacle", "GoalAlign", "PathAlign", "PathDist", "GoalDist"]
          BaseObstacle.scale: 0.02
          PathAlign.scale: 32.0
          GoalAlign.scale: 24.0
          PathAlign.forward_point_distance: 0.1
          GoalAlign.forward_point_distance: 0.1
          PathDist.scale: 32.0
          GoalDist.scale: 24.0
          RotateToGoal.scale: 32.0
          RotateToGoal.slowing_factor: 5.0
          RotateToGoal.lookahead_time: -1.0
    local_costmap:
      local_costmap:
        ros__parameters:
          enable_stamped_cmd_vel: true
          update_frequency: 5.0
          publish_frequency: 2.0
          global_frame: odom
          robot_base_frame: base_link
          rolling_window: true
          width: 3
          height: 3
          resolution: 0.06
          footprint: "[[ 0.189,  0.000],
                      [ 0.134, -0.134],
                      [ 0.000, -0.189],
                      [-0.134, -0.134],
                      [-0.189,  0.000],
                      [-0.134,  0.134],
                      [ 0.000,  0.189],
                      [ 0.134,  0.134]]"
          plugins: ["static_layer", "voxel_layer", "inflation_layer"]
          inflation_layer:
            plugin: "nav2_costmap_2d::InflationLayer"
            cost_scaling_factor: 4.0
            inflation_radius: 0.45
          voxel_layer:
            plugin: "nav2_costmap_2d::VoxelLayer"
            enabled: true
            publish_voxel_map: true
            origin_z: 0.0
            z_resolution: 0.05
            z_voxels: 16
            max_obstacle_height: 2.0
            mark_threshold: 0
            observation_sources: scan
            scan:
              topic: scan
              max_obstacle_height: 2.0
              clearing: true
              marking: true
              data_type: "LaserScan"
              raytrace_max_range: 3.0
              raytrace_min_range: 0.0
              obstacle_max_range: 2.5
              obstacle_min_range: 0.0
          static_layer:
            plugin: "nav2_costmap_2d::StaticLayer"
            map_subscribe_transient_local: true
          always_send_full_costmap: true
    
    global_costmap:
      global_costmap:
        ros__parameters:
          enable_stamped_cmd_vel: true
          update_frequency: 1.0
          publish_frequency: 1.0
          global_frame: map
          robot_base_frame: base_link
          footprint: "[[ 0.189,  0.000],
                      [ 0.134, -0.134],
                      [ 0.000, -0.189],
                      [-0.134, -0.134],
                      [-0.189,  0.000],
                      [-0.134,  0.134],
                      [ 0.000,  0.189],
                      [ 0.134,  0.134]]"
          resolution: 0.06
          track_unknown_space: true
          plugins: ["static_layer", "obstacle_layer", "inflation_layer"]
          obstacle_layer:
            plugin: "nav2_costmap_2d::ObstacleLayer"
            enabled: true
            observation_sources: scan
            scan:
              topic: scan
              max_obstacle_height: 2.0
              clearing: true
              marking: true
              data_type: "LaserScan"
              raytrace_max_range: 3.0
              raytrace_min_range: 0.0
              obstacle_max_range: 2.5
              obstacle_min_range: 0.0
          static_layer:
            plugin: "nav2_costmap_2d::StaticLayer"
            map_subscribe_transient_local: true
          inflation_layer:
            plugin: "nav2_costmap_2d::InflationLayer"
            cost_scaling_factor: 4.0
            inflation_radius: 0.45
          always_send_full_costmap: true
    
    planner_server:
      ros__parameters:
        enable_stamped_cmd_vel: true
        #expected_planner_frequency: 20.0
        planner_plugins: ["GridBased"]
        GridBased:
          plugin: "nav2_navfn_planner::NavfnPlanner"
          tolerance: 0.5
          use_astar: false
          allow_unknown: true
    
    smoother_server:
      ros__parameters:
        enable_stamped_cmd_vel: true
        smoother_plugins: ["simple_smoother"]
        simple_smoother:
          plugin: "nav2_smoother::SimpleSmoother"
          tolerance: 1.0e-10
          max_its: 1000
          do_refinement: true
    
    behavior_server:
      ros__parameters:
        enable_stamped_cmd_vel: true
        local_costmap_topic: local_costmap/costmap_raw
        global_costmap_topic: global_costmap/costmap_raw
        local_footprint_topic: local_costmap/published_footprint
        global_footprint_topic: global_costmap/published_footprint
        cycle_frequency: 10.0
        behavior_plugins: ["spin", "backup", "drive_on_heading", "assisted_teleop", "wait"]
        spin:
          plugin: "nav2_behaviors::Spin"
        backup:
          plugin: "nav2_behaviors::BackUp"
        drive_on_heading:
          plugin: "nav2_behaviors::DriveOnHeading"
        wait:
          plugin: "nav2_behaviors::Wait"
        assisted_teleop:
          plugin: "nav2_behaviors::AssistedTeleop"
        global_frame: map
        local_frame: odom
        robot_base_frame: base_link
        transform_tolerance: 0.1
        simulate_ahead_time: 2.0
        max_rotational_vel: 1.0
        min_rotational_vel: 0.4
        rotational_acc_lim: 3.2
    
    waypoint_follower:
      ros__parameters:
        enable_stamped_cmd_vel: true
        loop_rate: 20
        stop_on_failure: false
        action_server_result_timeout: 900.0
        waypoint_task_executor_plugin: "wait_at_waypoint"
        wait_at_waypoint:
          plugin: "nav2_waypoint_follower::WaitAtWaypoint"
          enabled: true
          waypoint_pause_duration: 200
    
    velocity_smoother:
      ros__parameters:
        enable_stamped_cmd_vel: true
        smoothing_frequency: 20.0
        scale_velocities: False
        feedback: "OPEN_LOOP"
        max_velocity: [0.26, 0.0, 1.0]
        min_velocity: [-0.26, 0.0, -1.0]
        max_accel: [2.5, 0.0, 3.2]
        max_decel: [-2.5, 0.0, -3.2]
        odom_topic: "odom"
        odom_duration: 0.1
        deadband_velocity: [0.0, 0.0, 0.0]
        velocity_timeout: 1.0
    
    collision_monitor:
      ros__parameters:
        enable_stamped_cmd_vel: true
        base_frame_id: "base_link"
        odom_frame_id: "odom"
        cmd_vel_in_topic: "cmd_vel_smoothed"
        cmd_vel_out_topic: "cmd_vel"
        state_topic: "collision_monitor_state"
        transform_tolerance: 0.2
        source_timeout: 1.0
        base_shift_correction: True
        stop_pub_timeout: 2.0
        # Polygons represent zone around the robot for "stop", "slowdown" and "limit" action types,
        # and robot footprint for "approach" action type.
        polygons: ["FootprintApproach"]
        FootprintApproach:
          type: "polygon"
          action_type: "approach"
          footprint_topic: "local_costmap/published_footprint"
          time_before_collision: 1.2
          simulation_time_step: 0.1
          min_points: 6
          visualize: False
          enabled: True
        observation_sources: ["scan"]
        scan:
          type: "scan"
          topic: "scan"
          min_height: 0.15
          max_height: 2.0
          enabled: True
    
    docking_server:
      ros__parameters:
        enable_stamped_cmd_vel: true
        controller_frequency: 50.0
        initial_perception_timeout: 5.0
        wait_charge_timeout: 5.0
        dock_approach_timeout: 30.0
        undock_linear_tolerance: 0.05
        undock_angular_tolerance: 0.1
        max_retries: 3
        base_frame: "base_link"
        fixed_frame: "odom"
        dock_backwards: false
        dock_prestaging_tolerance: 0.5
    
        # Types of docks
        dock_plugins: ['simple_charging_dock']
        simple_charging_dock:
          plugin: 'opennav_docking::SimpleChargingDock'
          docking_threshold: 0.05
          staging_x_offset: -0.7
          use_external_detection_pose: true
          use_battery_status: false # true
          use_stall_detection: false # true
    
          external_detection_timeout: 1.0
          external_detection_translation_x: -0.18
          external_detection_translation_y: 0.0
          external_detection_rotation_roll: -1.57
          external_detection_rotation_pitch: -1.57
          external_detection_rotation_yaw: 0.0
          filter_coef: 0.1
    
        # Dock instances
        # The following example illustrates configuring dock instances.
        # docks: ['home_dock']  # Input your docks here
        # home_dock:
        #   type: 'simple_charging_dock'
        #   frame: map
        #   pose: [0.0, 0.0, 0.0]
    
        controller:
          k_phi: 3.0
          k_delta: 2.0
          v_linear_min: 0.15
          v_linear_max: 0.15
    
    lifecycle_manager_navigation:
      ros__parameters:
        bond_timeout: 10.0
    ```
    

---

### 4.2 1차 변경

| Costmap | cost_scaling_factor | inflation_radius (m) |
| --- | --- | --- |
| Local | 1.0 | 0.20 |
| Global | 1.0 | 0.20 |

기본 대비 Local·Global의 반경을 0.45 → 0.20 m, 감쇠 계수를 4.0 → 1.0으로 변경했다. 반경 축소와 감쇠 완화가 동시에 적용되므로 각 변수의 영향을 분리하여 판단하기 어렵다.

![image.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DNav2%20parameter%20test/image%201.png)

관찰 결과: RViz 이미지 첨부. 주행 성공 여부·최소 이격 거리·주행 시간은 미기록.

---

### 4.3 2차 변경

| Costmap | cost_scaling_factor | inflation_radius (m) |
| --- | --- | --- |
| Local | 4.0 | 0.20 |
| Global | 1.0 | 0.20 |

1차 대비 Local의 감쇠 계수만 1.0 → 4.0으로 변경했다. Local 비용이 거리 증가에 따라 더 빠르게 감소하는 설정이다.

![image.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DNav2%20parameter%20test/image%202.png)

관찰 결과: RViz 이미지 첨부. 주행 성공 여부·최소 이격 거리·주행 시간은 미기록.

---

### 4.4 3차 변경

| Costmap | cost_scaling_factor | inflation_radius (m) |
| --- | --- | --- |
| Local | 2.0 | 0.60 |
| Global | 4.0 | 0.80 |

2차 대비 Local 반경을 0.20 → 0.60 m, 감쇠 계수를 4.0 → 2.0으로 변경했다. Global 반경은 0.20 → 0.80 m, 감쇠 계수는 1.0 → 4.0으로 변경했다. 설정 효과 설명이며 실제 주행 개선 여부는 추가 확인이 필요하다.

![image.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DNav2%20parameter%20test/image%203.png)

관찰 결과: RViz 이미지 첨부. 주행 성공 여부·최소 이격 거리·주행 시간은 미기록.

## 5. 현재 결론

기본 설정을 포함해 네 가지 inflation 조합을 기록했다. 현재 자료만으로 특정 조합이 가장 안전하거나 빠르다고 확정할 수는 없다. 3차 변경은 마지막으로 기록된 조합이며, 최종 채택 설정이라는 의미는 아니다.

비교 시에는 RViz의 비용 영역 변화와 실제 로봇의 주행 결과를 함께 확인해야 한다.

## 6. 후속 활용

nav에 존재하는 다양한 parameter 의미를 파악하고, 추후 개발 단계에서 필요한 값을 반복 활용이 가능하도록 한다.

https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/