# Homework_삐뽀삐뽀 소리내기 노드 만들기

> 원본: https://indecisive-freedom-6e8.notion.site/fff8e215779c839ca0bb8121f168801c  
> 최종 수정: 2026-10-02 10:24 / 변환: 2026-10-08 15:49

| 속성 | 값 |
|---|---|
| 환경 | ubuntu24.04,jazzy |
| 상태 | 완료 |
| 키워드 | workspace,package |
| 순서 | 2-0 |

### 📝 미션 수행

> 💡 **모든 작업은** **`rokey_venv`** **안에서 실행**해야 합니다.
>
> 터미널에 **(rokey_venv)** 가 없을 경우, **반드시** 아래 커맨드를 실행해 venv 환경을 활성화하세요.
>
> ```python
> source ~/venvs/rokey_venv/bin/activate
> ```

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

#### 삐뽀삐뽀 소리내기 노드 만들기

1. 코드 작성하기

   ```python
   #!/usr/bin/env python3
   
   """
   TurtleBot 4 repeating audio example.
   
   Equivalent behavior to:
   
       timeout 10 ros2 topic pub -r 0.5 /robot7/cmd_audio \
           irobot_create_msgs/msg/AudioNoteVector ...
   
   Behavior:
       - Publishes to /robot7/cmd_audio
       - Publishes once every 2 seconds (0.5 Hz)
       - Each message contains four notes:
             880 Hz for 0.3 s
             440 Hz for 0.3 s
             880 Hz for 0.3 s
             440 Hz for 0.3 s
       - Stops after 10 seconds
       - Handles Ctrl-C cleanly
   """
   
   import rclpy
   from rclpy.node import Node
   
   # ROS 2 message used by the Create 3/TurtleBot 4 audio interface.
   from irobot_create_msgs.msg import AudioNoteVector, AudioNote
   
   
   # ---------------------------------------------------------------------------
   # Configuration
   # ---------------------------------------------------------------------------
   
   # TurtleBot 4 namespace.
   # NOTE: UPDATE THIS VALUE to match your robot's namespace.
   ROBOT_NAMESPACE = "robot7"
   
   # Complete ROS 2 audio topic.
   AUDIO_TOPIC = f"/{ROBOT_NAMESPACE}/cmd_audio"
   
   # Equivalent to "ros2 topic pub -r 0.5".
   # 0.5 Hz means one message every 2 seconds.
   PUBLISH_RATE_HZ = 0.5
   
   # Equivalent to "timeout 10".
   RUN_TIME_SECONDS = 10.0
   
   # Duration of each individual note.
   NOTE_DURATION_SECONDS = 0
   NOTE_DURATION_NANOSECONDS = 300_000_000  # 0.3 seconds
   
   
   class TurtleBot4Beeper(Node):
       """ROS 2 node that repeatedly sends an audio sequence to TurtleBot 4."""
   
       def __init__(self):
           """Create the publisher, audio message, and timers."""
   
           # Give this ROS 2 node a descriptive name.
           super().__init__("tb4_beeper")
   
           # Create the publisher for the TurtleBot 4 audio command.
           #
           # Queue depth 10 is appropriate for these small, low-rate commands.
           self.audio_publisher = self.create_publisher(
               AudioNoteVector,
               AUDIO_TOPIC,
               10,
           )
   
           # Build the audio sequence once.
           # We reuse the same message for every publication.
           self.audio_message = self.create_audio_message()
   
           # Keep track of how many times the sequence has been published.
           self.publish_count = 0
   
           # Convert frequency to timer period:
           #
           #     period = 1 / frequency
           #
           # 0.5 Hz -> 2.0 seconds.
           publish_period = 1.0 / PUBLISH_RATE_HZ
   
           # Create the repeating timer.
           # ROS 2 calls publish_audio() every 2 seconds.
           self.publish_timer = self.create_timer(
               publish_period,
               self.publish_audio,
           )
   
           # Create a separate one-shot-style timer for the 10-second timeout.
           # We cancel this timer inside its callback so that it only fires once.
           self.stop_timer = self.create_timer(
               RUN_TIME_SECONDS,
               self.stop_node,
           )
   
           # This flag tells main() when the requested run time has expired.
           self.finished = False
   
           self.get_logger().info(
               f"Publishing audio to {AUDIO_TOPIC} at "
               f"{PUBLISH_RATE_HZ} Hz for {RUN_TIME_SECONDS:.1f} seconds."
           )
   
       def create_audio_message(self):
           """Construct the 880/440/880/440 Hz audio sequence."""
   
           # Create the complete audio-vector message.
           message = AudioNoteVector()
   
           # Equivalent to:
           #
           #     append: false
           #
           # A new command replaces the current audio sequence rather than
           # appending another sequence to the existing queue.
           message.append = False
   
           # Frequencies from the original CLI command.
           frequencies = [880, 440, 880, 440]
   
           # Create one AudioNote message for each frequency.
           for frequency in frequencies:
   
               # Create an individual audio note.
               note = AudioNote()
   
               # Set its audible frequency/pitch in Hz.
               note.frequency = frequency
   
               # Play this note for 0.3 seconds.
               note.max_runtime.sec = NOTE_DURATION_SECONDS
               note.max_runtime.nanosec = NOTE_DURATION_NANOSECONDS
   
               # Add this note to the complete sequence.
               message.notes.append(note)
   
           return message
   
       def publish_audio(self):
           """Publish one complete four-note audio sequence."""
   
           # Publish the AudioNoteVector message.
           self.audio_publisher.publish(self.audio_message)
   
           # Increment our diagnostic counter.
           self.publish_count += 1
   
           # Report exactly when a sequence was sent.
           self.get_logger().info(
               f"Published audio sequence #{self.publish_count}"
           )
   
       def stop_node(self):
           """Signal that the requested 10-second run has completed."""
   
           # Prevent this timer from firing again.
           self.stop_timer.cancel()
   
           # Tell the main loop to stop spinning.
           self.finished = True
   
           self.get_logger().info(
               f"10-second timeout reached. "
               f"Published {self.publish_count} sequences."
           )
   
   
   def main(args=None):
       """Initialize ROS 2, run the beeper, and shut down cleanly."""
   
       # Initialize the ROS 2 Python client library.
       rclpy.init(args=args)
   
       # Create our node.
       node = TurtleBot4Beeper()
   
       try:
           # Process ROS callbacks until the 10-second timeout occurs.
           while rclpy.ok() and not node.finished:
               # Process callbacks in small increments.
               #
               # The short timeout also allows Ctrl-C and our finished flag
               # to be handled promptly.
               rclpy.spin_once(node, timeout_sec=0.1)
   
       except KeyboardInterrupt:
           # Ctrl-C is a normal way for the operator to terminate the program.
           node.get_logger().info("Ctrl-C received. Stopping.")
   
       finally:
           # Destroy the ROS node and release DDS resources.
           node.destroy_node()
   
           # Shut down rclpy only if it has not already been shut down.
           if rclpy.ok():
               rclpy.shutdown()
   
   
   if __name__ == "__main__":
       main()
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
