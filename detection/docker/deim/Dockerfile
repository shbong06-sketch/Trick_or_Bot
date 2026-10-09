FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-devel

ARG DEIM_COMMIT=09d35d53d39ee3145a1e61e3a989b28b9468d1dd

RUN apt-get update && apt-get install -y --no-install-recommends \
    git libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/Intellindust-AI-Lab/DEIM.git /opt/deim \
    && git -C /opt/deim checkout --detach "${DEIM_COMMIT}" \
    && pip install --no-cache-dir -r /opt/deim/requirements.txt \
       "torch==2.5.1" "torchvision==0.20.1" "transformers<5" \
    && python /opt/deim/train.py --help

WORKDIR /workspace

CMD ["bash"]
