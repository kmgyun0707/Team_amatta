-- 모든 상태가 '분실'인 테스트 데이터
INSERT INTO item_lost (name, phone, category, color, gate, state)
VALUES
('김분실', '010-1111-2222', '카드지갑', '검정색', 1, '분실'),
('박미정', '010-3333-4444', '블루투스 이어폰', '화이트', 2, '분실'),
('이현우', '010-5555-6666', '백팩', '회색', 1, '분실'),
('최지수', '010-7777-8888', '태블릿', '스페이스그레이', 2, '분실'),
('정무명', '010-0000-0000', '장우산', '투명', 1, '분실');
-- 다양한 아이템 데이터 입력
INSERT INTO item (category, color, time,robot_name,location_x, location_y, image_path)
VALUES
('이어폰', 'black',  '2026-01-01 09:12:34', 'robot1', 1.23, -0.45, '/home/rokey/Desktop/amatta/static/item_01.png'),
('지갑',   'brown',  '2026-01-03 14:27:10', 'robot1', -0.80,  2.15, '/home/rokey/Desktop/amatta/static/item_02.png'),
('스마트폰','white', '2026-01-05 18:42:55', 'robot1',  0.35,  1.78, '/home/rokey/Desktop/amatta/static/item_03.png'),
('가방',   'black',  '2026-01-07 11:05:21', 'robot1', -1.45, -0.90, '/home/rokey/Desktop/amatta/static/item_04.png'),
('우산',   'blue',   '2026-01-09 20:19:03', 'robot1',  2.10,  0.55, '/home/rokey/Desktop/amatta/static/item_05.png'),
('이어폰', 'white',  '2026-01-12 08:33:47', 'robot1', -0.25,  1.10, '/home/rokey/Desktop/amatta/static/item_06.png'),
('지갑',   'black',  '2026-01-14 16:51:09', 'robot1',  1.90, -1.20, '/home/rokey/Desktop/amatta/static/item_07.png'),
('스마트폰','black', '2026-01-17 13:02:44', 'robot3', -2.30,  0.40, '/home/rokey/Desktop/amatta/static/item_08.png'),
('가방',   'gray',   '2026-01-19 19:48:12', 'robot3',  0.75, -2.10, '/home/rokey/Desktop/amatta/static/item_09.png'),
('우산',   'red',    '2026-01-22 10:26:58', 'robot3', -1.10,  2.45, '/home/rokey/Desktop/amatta/static/item_10.png'),
('이어폰', 'pink',   '2026-01-24 15:39:36', 'robot3',  2.60, -0.30, '/home/rokey/Desktop/amatta/static/item_11.png'),
('지갑',   'navy',   '2026-01-26 09:14:05', 'robot3', -0.60, -1.75, '/home/rokey/Desktop/amatta/static/item_12.png'),
('스마트폰','blue',  '2026-01-28 21:07:41', 'robot3',  1.15,  1.35, '/home/rokey/Desktop/amatta/static/item_13.png'),
('가방',   'green',  '2026-01-30 12:55:18', 'robot3', -2.00, -0.80, '/home/rokey/Desktop/amatta/static/item_14.png'),
('우산',   'black',  '2026-02-01 17:22:49', 'robot3',  0.40,  2.05, '/home/rokey/Desktop/amatta/static/item_15.png'),
('이어폰', 'gray',   '2026-02-02 08:41:07', 'robot3', -1.55,  0.95, '/home/rokey/Desktop/amatta/static/item_16.png'),
('지갑',   'red',    '2026-02-03 14:36:52', 'robot3',  2.25, -1.60, '/home/rokey/Desktop/amatta/static/item_17.png'),
('스마트폰','silver','2026-02-04 10:09:33', 'robot3', -0.95,  1.85, '/home/rokey/Desktop/amatta/static/item_18.png'),
('가방',   'brown',  '2026-02-04 18:58:26', 'robot3',  1.60, -0.50, '/home/rokey/Desktop/amatta/static/item_19.png'),
('우산',   'yellow', '2026-02-05 09:03:11', 'robot3', -2.40,  0.20, '/home/rokey/Desktop/amatta/static/item_20.png');

INSERT INTO location (loc_id, loc_name) 
VALUES
(0, '입구'),
(1, '은행'),
(2, '카운터'),
(3, '벤치1'),
(4, '벤치2'),
(5, '여자화장실'),
(6, '면세점'),
(7, '남자화장실'),
(8, 'gate 1'),
(9, 'gate 2');