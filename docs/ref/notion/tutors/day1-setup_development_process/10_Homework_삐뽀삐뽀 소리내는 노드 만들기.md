# Homework_삐뽀삐뽀 소리내는 노드 만들기

> 원본: https://indecisive-freedom-6e8.notion.site/4938e215779c82bbbb4e01ba546bcd52  
> 최종 수정: 2026-10-02 09:13 / 변환: 2026-10-08 15:49

| 속성 | 값 |
|---|---|
| 환경 | ubuntu22.04,humble,ubuntu24.04,jazzy |
| 상태 | 완료 |
| 키워드 | workspace,package |
| 순서 | 1-9 |

> 💡 **모든 작업은** **`rokey_venv`** **안에서 실행**해야 합니다.
>
> 터미널에 **(rokey_venv)** 가 없을 경우, **반드시** 아래 커맨드를 실행해 venv 환경을 활성화하세요.
>
> ```python
> source ~/venvs/rokey_venv/bin/activate
> ```

### 미션 수행

CLI로 동작 확인

    ```bash
    timeout 4 ros2 topic pub -r 1 robot<n>/cmd_audio \
    irobot_create_msgs/msg/AudioNoteVector \
    "{header: {frame_id: ''}, append: false, notes: [
      {frequency: 880, max_runtime: {sec: 0, nanosec: 300000000}},
      {frequency: 440, max_runtime: {sec: 0, nanosec: 300000000}},
      {frequency: 880, max_runtime: {sec: 0, nanosec: 300000000}},
      {frequency: 440, max_runtime: {sec: 0, nanosec: 300000000}}
    ]}"
    ```

    - 각 음이 **0.3초(300ms)** 재생됨

    - `880Hz`와 `440Hz`를 번갈아 재생 → 경고음 같은 효과

    - Do you hear all four sounds?

CLI로 동작 확인

    ```bash
    timeout 4 ros2 topic pub -r 0.5 robot<n>/cmd_audio \
    irobot_create_msgs/msg/AudioNoteVector \
    "{header: {frame_id: ''}, append: false, notes: [
      {frequency: 880, max_runtime: {sec: 0, nanosec: 300000000}},
      {frequency: 440, max_runtime: {sec: 0, nanosec: 300000000}},
      {frequency: 880, max_runtime: {sec: 0, nanosec: 300000000}},
      {frequency: 440, max_runtime: {sec: 0, nanosec: 300000000}}
    ]}"
    ```

    - what is the difference?

    - how many times do you hear the sound sequence?

    - what is the command to hear the complete sound sequence 4 times

#### 삐뽀삐뽀 소리내는 노드 만들기

1. 코드 작성하기

   ```python
   #Homework
   ```

2. setup.py 수정

   `~/rokey_ws/src/turtlebot4_beep/setup.py`

   ```python
       entry_points={
           'console_scripts': [
               'beep_node = turtlebot4_beep.beep_node:main'
           ],
       },
   ```

3. package.xml수정

   `<exec_depend>` 항목 추가

   ```xml
   <exec_depend>rclpy</exec_depend>
   <exec_depend>irobot_create_msgs</exec_depend>
   <exec_depend>builtin_interfaces</exec_depend>
   ```

4. 빌드 및 환경 설정

   ```bash
   cd ~/rokey_ws
   colcon build colcon build --symlink-install --packages-select turtlebot4_beep
   source install/setup.bash
   ```

5. 빌드 및 환경 설정

   ```bash
   ros2 run turtlebot4_beep beep_node
   ```
