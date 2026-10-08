# Localization Recovery

> 원본: https://indecisive-freedom-6e8.notion.site/1748e215779c82e898ef8102859cf1c6  
> 최종 수정: 2026-08-20 12:39 / 변환: 2026-10-08 15:50

| 속성 | 값 |
|---|---|
| 순서 | 5-1 |

```bash
#When localization is not coming up

$ ros2 lifecycle get /robot<n>/map_server
$ ros2 lifecycle get /robot<n>/amcl

$ ros2 lifecycle set /robot<n>/map_server configure
$ ros2 lifecycle set /robot<n>/map_server activate

$ ros2 lifecycle set /robot<n>/amcl configure
$ ros2 lifecycle set /robot<n>/amcl activate

```
