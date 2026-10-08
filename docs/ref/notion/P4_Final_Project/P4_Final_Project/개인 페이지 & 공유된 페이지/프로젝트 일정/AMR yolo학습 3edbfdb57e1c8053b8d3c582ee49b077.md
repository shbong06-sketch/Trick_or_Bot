# AMR yolo학습

날짜: 2026년 10월 2일

1. 패키지 설치 (venv 안에서)
pip install -U ultralytics pandas openpyxl
YOLO26을 쓰려면 ultralytics 8.4 이상이 필요해서 -U로 업데이트합니다.
2. 실행

```jsx
cd ~/minicar_ws/yolo_compare
export ROBOFLOW_API_KEY="본인키"
python3 train_compare.py

옵션 예시:
python3 train_compare.py --epochs 50 --batch 8
python3 train_compare.py --models yolov8n.pt yolo26n.pt   # 일부만
```