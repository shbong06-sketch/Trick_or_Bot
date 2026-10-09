FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-devel

ARG RTDETR_COMMIT=df2a96c8c3a098567a1149bf0248da6efe6d495d

RUN apt-get update && apt-get install -y --no-install-recommends \
    git libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/lyuwenyu/RT-DETR.git /opt/rtdetr \
    && git -C /opt/rtdetr checkout --detach "${RTDETR_COMMIT}" \
    && pip install --no-cache-dir -r /opt/rtdetr/rtdetrv2_pytorch/requirements.txt \
       "torch==2.5.1" "torchvision==0.20.1" \
    && python -c "from pycocotools.coco import COCO" \
    && python /opt/rtdetr/rtdetrv2_pytorch/tools/train.py --help

WORKDIR /workspace

CMD ["bash"]
