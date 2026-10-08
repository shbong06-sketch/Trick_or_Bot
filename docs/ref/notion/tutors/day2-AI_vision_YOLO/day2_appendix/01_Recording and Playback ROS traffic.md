# Recording and Playback ROS traffic

> 원본: https://indecisive-freedom-6e8.notion.site/0c98e215779c82609afd01f37fa01e8f  
> 최종 수정: 2026-07-24 17:44 / 변환: 2026-10-08 14:05

| 속성 | 값 |
|---|---|
| 상태 | 완료 |
| 차시 | 2-9-3 |

> 💡 **모든 작업은** **`rokey_venv`** **안에서 실행**해야 합니다.
>
> 터미널에 **(rokey_venv)** 가 없을 경우, **반드시** 아래 커맨드를 실행해 venv 환경을 활성화하세요.
>
> ```python
> source ~/venvs/rokey_venv/bin/activate
> ```

Create or move to a directory to store the recordings

```bash
cd Documents/bags
```

```bash
#record all traffics
ros2 bag record -a
```

```bash
# playback recording
# make sure source /etc/turtlebot4_discovery/setup.bash is commented out first in .bashrc

ros2 bag play --loop rosbag2_2025_06_25-09_10_18/
```
