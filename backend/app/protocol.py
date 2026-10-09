import struct

# /ws/video 바이너리 프레임 = 44바이트 헤더 + JPEG 원본 (little-endian)
#   u8 ver | u8 flags | u16 reserved | u32 seq | f64 stamp(s) | f32×7 x,y,z,qx,qy,qz,qw
# 포즈는 촬영 시각 기준 map → 카메라 광학 프레임 변환 (map 기준 카메라 자세)
VIDEO_HEADER = struct.Struct("<BBHIdfffffff")
VIDEO_VER = 1
FLAG_POSE = 0x01

Pose7 = tuple[float, float, float, float, float, float, float]


def pack_video_frame(seq: int, stamp: float, pose: Pose7 | None, jpeg: bytes) -> bytes:
    flags = FLAG_POSE if pose is not None else 0
    header = VIDEO_HEADER.pack(VIDEO_VER, flags, 0, seq & 0xFFFFFFFF, stamp, *(pose or (0.0,) * 7))
    return header + jpeg
