# web/location_mapper.py
ROBOT_PLACES = {
    "robot1": {
        "Entrance": (-3.26, 3.71),
        "Bank": (-2.39, 3.15),
        "Counter": (-0.54, 3.64),
        "Bench_1": (-0.54, 2.12),
        "Bench_2": (-0.83, 0.80),
        "Ladies_Room": (-0.486, -0.75),
        "Duty_Free": (-1.99, 0.82),
        "Mens_Room": (-3.29, 2.6),
        "Gate1": (-0.60, -1.31),
        "Gate2": (-2.13, -1.37),
    },
    "robot3": {
        "Entrance": (-3.26, 3.77),
        "Bank": (-2.08, 3.45),
        "Counter": (-0.584, 3.64),
        "Bench_1": (-0.791, 2.19),
        "Bench_2": (-0.672, 0.615),
        "Ladies_Room": (-0.547, -0.636),
        "Duty_Free": (-2.35, 0.799),
        "Mens_Room": (-3.16, 2.58),
        "Gate1": (-0.76, -1.59),
        "Gate2": (-2.18, -1.26),
    },
}

# ✅ UI에 보여줄 한글명
KOR_LABEL = {
    "Entrance": "입구",
    "Bank": "은행",
    "Counter": "카운터",
    "Bench_1": "벤치 1",
    "Bench_2": "벤치 2",
    "Ladies_Room": "여자화장실",
    "Mens_Room": "남자화장실",
    "Duty_Free": "면세점",
    "Gate1": "게이트 1",
    "Gate2": "게이트 2",
}

def _dist2(x, y, ref):
    return (x - ref[0])**2 + (y - ref[1])**2

def xy_to_place_korean(robot: str, x: float, y: float, tolerance_m: float = 0.9) -> str:
    """
    로봇별 기준 좌표표에서 (x,y)에 가장 가까운 장소를 찾고,
    tolerance_m 이내면 한글 위치명 반환, 아니면 '알 수 없음'
    """
    places = ROBOT_PLACES.get(robot)
    if not places or x is None or y is None:
        return "알 수 없음"

    best_key = None
    best_d2 = None
    for key, ref in places.items():
        d2 = _dist2(float(x), float(y), ref)
        if best_d2 is None or d2 < best_d2:
            best_d2 = d2
            best_key = key

    if best_key is None:
        return "알 수 없음"

    if best_d2 <= (tolerance_m ** 2):
        return KOR_LABEL.get(best_key, best_key)

    return "알 수 없음"
