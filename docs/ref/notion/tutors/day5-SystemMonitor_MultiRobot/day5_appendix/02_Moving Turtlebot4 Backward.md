# Moving Turtlebot4 Backward

> 원본: https://indecisive-freedom-6e8.notion.site/c288e215779c83f88ef68139c5b7ec93  
> 최종 수정: 2026-07-23 10:34 / 변환: 2026-10-08 14:07

1. Check current setting

```bash
ros2 param get /<robot_n>/_do_not_use/motion_control safety_override
```

```bash
#you should see
String value is: none
```

2. Change the parameter to enable backing up

```bash
ros2 param set /<robot_n>/_do_not_use/motion_control safety_override backup_only
```

```bash
ros2 param get /<robot_n>/_do_not_use/motion_control safety_override
```

```bash
#you should see
String value is: backup_only
```

3. Try backing up

```bash
ros2 topic pub /robot<n>/cmd_vel geometry_msgs/msg/TwistStamped "{twist: {linear: {x: -0.1}}}" -r 10
```

> 💡 
> #### 4. How to make the override *stick* with Nav2
>
> If you want your TurtleBot4 to back up freely even after nav2/localization launches and after reboots:
>
> 1. Open the **Create3 web interface** (connect to its IP in a browser).
>
> 2. Go to the Application / ROS 2 Parameters File section.
>
> 3. In the YAML, set:
>
>    ```bash
>    motion_control:
>      ros__parameters:
>        safety_override: "backup_only"   # or "full"
>    ```
>
>
> 4. Save and **restart the application** (or power-cycle the base).
>
> Now each time you launch:
>
>     ```bash
>     ros2 launch turtlebot4_navigation localization.launch.py ...
>     ros2 launch turtlebot4_navigation nav2.launch.py ...
>     ```
>
> the base will come up with `safety_override` already set to `backup_only` or `full`, and nav2 will just send `/cmd_vel` into that environment.
>
> You can verify with:
>
> ```bash
> ros2 param get /motion_control safety_override
> # Should show backup_only or full before and after nav2.launch.py
> ```

To change the parameter at runtime with python code:

```bash
import rclpy
from rclpy.node import Node
from rcl_interfaces.msg import Parameter, ParameterValue
from rcl_interfaces.srv import SetParameters

class SafetySetter(Node):
    def __init__(self):
        super().__init__("set_safety")
        self.cli = self.create_client(SetParameters, "/motion_control/set_parameters")
        self.cli.wait_for_service()

    def set_backup_only(self):
        req = SetParameters.Request()
        req.parameters.append(
            Parameter(
                name="safety_override",
                value=ParameterValue(type=ParameterValue.TYPE_STRING, string_value="backup_only")
            )
        )
        future = self.cli.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        self.get_logger().info(f"Result: {future.result().results[0].successful}")

rclpy.init()
node = SafetySetter()
node.set_backup_only()
rclpy.shutdown()
```
