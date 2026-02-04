#DB에 분실물 존재 여부
bool registered

# 분실물이 DB에 있을 경우 사용
int32 item_id
int32 counter

# 분실물이 DB에 없을 경우 사용
int32[] visited_spots
int32 gate_id
