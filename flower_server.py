# -*- coding: utf-8 -*-
"""花卉养殖助手 - Flask后端服务器 (SQLite数据库)"""

import os
import json
import hashlib
import sqlite3
import uuid
import re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, g

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=WORK_DIR)

DB_PATH = os.path.join(WORK_DIR, 'flower_care.db')
HTML_PATH = os.path.join(WORK_DIR, 'flower-care.html')

# ==================== DATABASE ====================
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """初始化数据库表和花卉知识数据"""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    # 用户表
    db.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        city TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )''')

    # 花卉知识表
    db.execute('''CREATE TABLE IF NOT EXISTS flower_knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        flower_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        emoji TEXT DEFAULT '',
        photo TEXT DEFAULT '',
        photos TEXT DEFAULT '[]',
        photo_labels TEXT DEFAULT '[]',
        desc TEXT DEFAULT '',
        soil TEXT DEFAULT '',
        spring_water TEXT DEFAULT '',
        spring_fertilize TEXT DEFAULT '',
        spring_tips TEXT DEFAULT '',
        summer_water TEXT DEFAULT '',
        summer_fertilize TEXT DEFAULT '',
        summer_tips TEXT DEFAULT '',
        autumn_water TEXT DEFAULT '',
        autumn_fertilize TEXT DEFAULT '',
        autumn_tips TEXT DEFAULT '',
        winter_water TEXT DEFAULT '',
        winter_fertilize TEXT DEFAULT '',
        winter_tips TEXT DEFAULT '',
        grafting TEXT DEFAULT '',
        repot TEXT DEFAULT ''
    )''')

    # 用户花卉表
    db.execute('''CREATE TABLE IF NOT EXISTS user_flowers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        flower_id TEXT NOT NULL,
        added_at TEXT DEFAULT (datetime('now','localtime')),
        last_water TEXT,
        last_fertilize TEXT,
        last_repot TEXT,
        UNIQUE(user_id, flower_id),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(flower_id) REFERENCES flower_knowledge(flower_id) ON DELETE CASCADE
    )''')

    # 养护记录表
    db.execute('''CREATE TABLE IF NOT EXISTS care_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        flower_id TEXT NOT NULL,
        action TEXT NOT NULL,
        date TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )''')

    # 通用花卉知识专题表
    db.execute('''CREATE TABLE IF NOT EXISTS knowledge_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic_id TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        content TEXT DEFAULT ''
    )''')

    # 用户花卉排序表
    db.execute('''CREATE TABLE IF NOT EXISTS user_flower_orders (
        user_id INTEGER PRIMARY KEY,
        flower_order TEXT DEFAULT '[]',
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )''')

    # 我的植株表
    db.execute('''CREATE TABLE IF NOT EXISTS my_plants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        flower_id TEXT NOT NULL,
        plant_name TEXT NOT NULL,
        custom_water_days INTEGER,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(flower_id) REFERENCES flower_knowledge(flower_id) ON DELETE CASCADE
    )''')

    # 浇水计划表
    db.execute('''CREATE TABLE IF NOT EXISTS water_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plant_id INTEGER NOT NULL,
        plan_date TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        actual_date TEXT,
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(plant_id) REFERENCES my_plants(id) ON DELETE CASCADE
    )''')

    db.commit()

    # 迁移：给已有 my_plants 表添加 custom_water_days 字段
    try:
        db.execute('ALTER TABLE my_plants ADD COLUMN custom_water_days INTEGER')
    except Exception:
        pass  # 字段已存在

    # 迁移：给 my_plants 表添加 photo 和 identify_result 字段
    try:
        db.execute('ALTER TABLE my_plants ADD COLUMN photo TEXT DEFAULT ""')
    except Exception:
        pass
    try:
        db.execute('ALTER TABLE my_plants ADD COLUMN identify_result TEXT DEFAULT ""')
    except Exception:
        pass

    # 迁移：给 water_plans 表添加 reminder_status 字段（pending/confirmed/kept）
    try:
        db.execute('ALTER TABLE water_plans ADD COLUMN reminder_status TEXT DEFAULT "pending"')
    except Exception:
        pass
    # 迁移：给 water_plans 表添加 reminder_updated 字段
    try:
        db.execute('ALTER TABLE water_plans ADD COLUMN reminder_updated TEXT')
    except Exception:
        pass

    # 迁移：给 users 表添加 avatar 字段
    try:
        db.execute('ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT ""')
    except Exception:
        pass

    # 用户花卉显示配置表（控制养花知识栏目中花卉的可见性和排序）
    db.execute('''CREATE TABLE IF NOT EXISTS user_flower_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        flower_id TEXT NOT NULL,
        visible INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        UNIQUE(user_id, flower_id),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(flower_id) REFERENCES flower_knowledge(flower_id) ON DELETE CASCADE
    )''')

    db.commit()
    count = db.execute("SELECT COUNT(*) FROM flower_knowledge").fetchone()[0]
    if count == 0:
        init_flower_data(db)
        init_knowledge_topics(db)

    db.close()

def init_flower_data(db):
    """插入20种花卉知识数据（图片已本地化）"""
    flowers = [
        ('rose', '月季', '🌹',
         '/images/rose-cover.jpg',
         json.dumps(['/images/rose-closeup.jpg', '/images/rose-full.jpg', '/images/rose-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '花中皇后，四季开花，品种繁多',
         '疏松肥沃的微酸性土壤，腐叶土+园土+河沙(4:3:3)',
         '3-4天','15天一次稀薄液肥','修剪枯枝，新芽萌动期追肥',
         '1-2天','停止浓肥，可用薄肥','高温遮阴，通风防病，早晚浇水',
         '3-4天','20天一次复合肥','秋花修剪，减少氮肥增磷钾',
         '7-10天','停止施肥','重剪整形，清园防虫',
         '可用野蔷薇作砧木，春季芽接或秋季劈接，接穗选半木质化枝条',
         '2-3年换盆一次，早春萌芽前进行，修剪老根烂根'),
        ('orchid', '兰花', '🪻',
         '/images/orchid-cover.jpg',
         json.dumps(['/images/orchid-closeup.jpg', '/images/orchid-full.jpg', '/images/orchid-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '幽雅高洁，国香之首，品种丰富',
         '兰花专用植料：树皮+兰石+水苔(3:3:4)，透气为要',
         '5-7天','20天一次稀薄液肥','分株繁殖好时机，逐步增加光照',
         '2-3天','薄肥勤施，15天一次','遮阴60-70%，通风降温，忌烈日',
         '4-5天','增施磷钾肥促花','增加光照促花芽分化，减少氮肥',
         '7-10天','停止施肥','入室保暖5°C以上，控制浇水',
         '兰花一般不嫁接，以分株繁殖为主，3-4月或9-10月进行',
         '2年换盆一次，春秋均可，剪除腐根，新盆垫高排水层'),
        ('jasmine', '茉莉花', '🤍',
         '/images/jasmine-cover.jpg',
         json.dumps(['/images/jasmine-closeup.jpg', '/images/jasmine-full.jpg', '/images/jasmine-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '清香宜人，夏日必备，花开不绝',
         '微酸性腐殖土，腐叶土+园土+河沙(4:4:2)',
         '3-5天','15天一次稀薄饼肥水','出室后修剪整形，逐步增加浇水量',
         '1-2天','7-10天一次液肥','盛花期需水量大，早晚浇透，花后修剪',
         '3-4天','20天一次磷钾肥','减少氮肥，增施磷钾促花，入秋逐步入室',
         '7-10天','停止施肥','保暖10°C以上，少浇水保微润',
         '扦插为主，春夏季选半木质化枝条，插入沙床20天生根',
         '每年或隔年换盆，春季出房后进行，修剪老根'),
        ('sunflower', '向日葵', '🌻',
         '/images/sunflower-cover.jpg',
         json.dumps(['/images/sunflower-closeup.jpg', '/images/sunflower-full.jpg', '/images/sunflower-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '阳光热情，向着光明，生命力强',
         '疏松透气排水好的壤土，园土+腐叶土+河沙(5:3:2)',
         '5-7天','20天一次复合肥','播种繁殖，保证充足阳光',
         '1-2天','15天一次磷钾肥','全天日照，高温多浇水，注意防风',
         '3-5天','减少施肥','采收种子，清理残株',
         '无需','无需','一年生花卉，冬季不可室外越冬',
         '向日葵不嫁接，以播种繁殖为主，春播3-4月',
         '一般不换盆，直接播种于定植盆中'),
        ('chrysanthemum', '菊花', '🌼',
         '/images/chrysanthemum-cover.jpg',
         json.dumps(['/images/chrysanthemum-closeup.jpg', '/images/chrysanthemum-full.jpg', '/images/chrysanthemum-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '秋菊傲霜，品种繁多，观赏性极佳',
         '肥沃疏松排水好的壤土，腐叶土+园土+河沙(4:4:2)',
         '5-7天','20天一次稀薄液肥','分株扦插繁殖，摘心促分枝',
         '2-3天','15天一次复合肥','遮阴避暑，防治蚜虫红蜘蛛',
         '3-4天','10天一次磷钾肥','现蕾期增施磷钾，抹侧蕾保主蕾',
         '7-10天','停止施肥','花后剪去残茎，留根基越冬',
         '可嫁接，以青蒿或白蒿为砧木，5-6月劈接',
         '每年换盆，春季进行，更新土壤'),
        ('peony', '牡丹', '🏵️',
         '/images/peony-cover.jpg',
         json.dumps(['/images/peony-closeup.jpg', '/images/peony-full.jpg', '/images/peony-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '国色天香，雍容华贵，花中之王',
         '深厚肥沃排水好的中性壤土，忌酸性土',
         '5-7天','萌芽期追施一次饼肥','花前追肥，花后去残花，防倒伏',
         '3-5天','花后追肥一次复合肥','遮阴降温，防积水烂根',
         '5-7天','施一次越冬基肥','落叶后清园，秋分前后可分株',
         '15-20天','停止施肥','培土防寒，北方注意覆膜保暖',
         '以芍药根为砧木，9-10月掘接，选充实芽眼',
         '4-5年换盆一次，秋季进行，少伤根'),
        ('lily', '百合', '🪷',
         '/images/lily-cover.jpg',
         json.dumps(['/images/lily-closeup.jpg', '/images/lily-full.jpg', '/images/lily-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '百年好合，清雅芬芳，球根花卉',
         '肥沃疏松微酸性沙壤土，腐叶土+园土+沙(5:3:2)',
         '5-7天','15天一次稀薄液肥','种球种植，覆盖5-8cm土',
         '2-3天','花期追施磷钾肥','遮阴50%，通风防病，花后剪花茎',
         '5-7天','花后追肥一次','叶枯后挖球储藏，放阴凉通风处',
         '不需','停止施肥','种球低温储藏，5°C左右春化',
         '百合不嫁接，以鳞片扦插或分球繁殖',
         '每年换盆换土，春季种植时进行'),
        ('camellia', '茶花', '🌺',
         '/images/camellia-cover.jpg',
         json.dumps(['/images/camellia-closeup.jpg', '/images/camellia-full.jpg', '/images/camellia-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '冬春盛放，花大色艳，四季常绿',
         '酸性腐殖土，山泥+腐叶土+河沙(5:3:2)，忌碱性土',
         '3-4天','花后追施氮肥恢复','花后修剪整形，摘除残花',
         '1-2天','薄肥勤施，磷钾为主','遮阴防晒，叶面喷水降温，防日灼',
         '3-4天','10天一次磷钾肥','增施磷钾促花蕾，疏蕾每枝留1个',
         '5-7天','花期可少量追肥','防冻0°C以上，室内明亮处，控制浇水',
         '春季靠接或劈接，砧木用油茶，接穗选当年生枝',
         '2-3年换盆，花后进行，带土球移栽'),
        ('narcissus', '水仙', '🥀',
         '/images/narcissus-cover.jpg',
         json.dumps(['/images/narcissus-closeup.jpg', '/images/narcissus-full.jpg', '/images/narcissus-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '凌波仙子，清雅淡香，水培即可',
         '水培无需土壤，土培用腐叶土+园土+沙(4:4:2)',
         '水培1-2天换水','不需施肥','花后可土培养球，留叶养球',
         '休眠期不需水','停止施肥','鳞茎休眠，放阴凉通风处储存',
         '开始水培1-2天换水','水培不需施肥','10-11月选购种球，开始水培',
         '1-2天换水','不需施肥','花期控温10-15°C延长花期，晒太阳防徒长',
         '水仙不嫁接，以分球繁殖为主',
         '每年新球重新种植，水培无需换盆'),
        ('hydrangea', '绣球花', '💜',
         '/images/hydrangea-cover.jpg',
         json.dumps(['/images/hydrangea-closeup.jpg', '/images/hydrangea-full.jpg', '/images/hydrangea-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '花团锦簇，颜色可调，庭院佳品',
         '疏松肥沃微酸性土，酸性开蓝花，碱性开粉花',
         '3-4天','15天一次复合肥','萌芽期追肥，调蓝可施硫酸铝',
         '1-2天','花期追施磷钾肥','遮阴50%，叶面喷水，花后修剪',
         '4-5天','施一次越冬肥','花后修剪只去花球，不剪老枝',
         '7-10天','停止施肥','防寒保暖，大花绣球老枝越冬勿重剪',
         '绣球不嫁接，以扦插和分株繁殖',
         '1-2年换盆，春季进行，根系发达需大盆'),
        ('gardenia', '栀子花', '🤍',
         '/images/gardenia-cover.jpg',
         json.dumps(['/images/gardenia-closeup.jpg', '/images/gardenia-full.jpg', '/images/gardenia-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '洁白芳香，南花北养的经典',
         '酸性腐殖土，山泥+腐叶土+河沙(5:3:2)',
         '3-5天','15天一次矾肥水','出室渐见阳光，定期施硫酸亚铁',
         '1-2天','7-10天一次薄肥','遮阴通风，叶面喷水，防黄叶',
         '3-5天','20天一次磷钾肥','减少氮肥，增施磷钾促来年花芽',
         '7-10天','停止施肥','保暖5°C以上，少浇水，防冻伤',
         '扦插繁殖为主，4-5月选半木质化枝条扦插',
         '2年换盆一次，春季进行，需酸性土'),
        ('cactus', '仙人掌', '🌵',
         '/images/cactus-cover.jpg',
         json.dumps(['/images/cactus-closeup.jpg', '/images/cactus-full.jpg', '/images/cactus-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '顽强坚韧，省心易养，观花观刺',
         '疏松透气的沙质土，园土+腐叶土+粗沙+炉渣(3:2:3:2)',
         '7-10天','20天一次稀薄液肥','生长旺季开始，适当增加浇水',
         '5-7天','15天一次磷钾肥','部分品种花期，避免淋雨，通风',
         '7-10天','减少施肥','逐渐减少浇水，准备休眠',
         '15-20天或断水','停止施肥','休眠期控水，5°C以上越冬',
         '常用三棱箭作砧木嫁接蟹爪兰等，春夏劈接',
         '2-3年换盆，春季进行，小心刺手'),
        ('succulent', '多肉植物', '🪴',
         '/images/succulent-cover.jpg',
         json.dumps(['/images/succulent-closeup.jpg', '/images/succulent-full.jpg', '/images/succulent-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '萌趣可爱，品种繁多，懒人首选',
         '颗粒土为主，泥炭+颗粒(3:7)，颗粒可用麦饭石、赤玉土',
         '7-10天','30天一次稀薄液肥','生长旺季，可叶插扦插繁殖',
         '10-15天(傍晚浇)','停止施肥','遮阴通风防黑腐，控水度夏',
         '7-10天','30天一次稀薄肥','恢复生长，上色好季节，增加光照',
         '15-20天','停止施肥','5°C以下断水防冻，室内向阳处',
         '多肉可嫁接，用大戟科砧木嫁接，但不常见',
         '1-2年换盆，春秋进行，修根晾根后上盆'),
        ('bougainvillea', '三角梅', '🌸',
         '/images/bougainvillea-cover.jpg',
         json.dumps(['/images/bougainvillea-closeup.jpg', '/images/bougainvillea-full.jpg', '/images/bougainvillea-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '花开满墙，色彩浓烈，南方庭院常见',
         '疏松肥沃排水好的土壤，腐叶土+园土+沙(4:4:2)',
         '3-5天','15天一次复合肥','修剪整形，增加光照，促新枝',
         '1-2天','控水促花后追磷钾肥','控水促花：浇水等叶片微蔫再浇透',
         '3-4天','花后追肥一次','秋季可再控水促一波花',
         '7-10天','停止施肥','10°C以上越冬，北方入室，控水',
         '可嫁接多色花，春季劈接，同一株上开不同色花',
         '2年换盆，春季进行，盆不宜过大'),
        ('begonia', '海棠', '🌷',
         '/images/begonia-cover.jpg',
         json.dumps(['/images/begonia-closeup.jpg', '/images/begonia-full.jpg', '/images/begonia-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '花姿潇洒，富贵美丽，传统名花',
         '肥沃疏松微酸性土壤，腐叶土+园土+河沙(4:3:3)',
         '3-5天','花前追施磷钾肥','花期赏花，花后修剪残花',
         '2-3天','15天一次薄肥','遮阴避暑，通风防病',
         '4-5天','施一次越冬基肥','秋季修剪整形，施基肥',
         '10-15天','停止施肥','休眠期控水，防寒保暖',
         '海棠嫁接常用海棠实生苗作砧木，春季劈接',
         '2-3年换盆，春季花后进行'),
        ('clivia', '君子兰', '🧡',
         '/images/clivia-cover.jpg',
         json.dumps(['/images/clivia-closeup.jpg', '/images/clivia-full.jpg', '/images/clivia-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '花叶并美，雍容大气，室内佳品',
         '疏松透气微酸性腐殖土，腐叶土+松针+河沙(5:3:2)',
         '5-7天','15天一次饼肥水','花期管理，人工授粉可结实',
         '3-4天','薄肥少施','遮阴通风，25°C以上半休眠少浇水',
         '5-7天','增施磷钾促花','增大温差促花箭，8-10°C低温处理',
         '7-10天','少量磷钾肥促花','花期控温10-15°C，见干见湿',
         '君子兰不嫁接，分株或播种繁殖',
         '1-2年换盆，春秋进行，忌深栽'),
        ('jade_plant', '玉树', '🪴',
         '/images/jade_plant-cover.jpg',
         json.dumps(['/images/jade_plant-closeup.jpg', '/images/jade_plant-full.jpg', '/images/jade_plant-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '厚叶常绿，古桩苍劲，寓意吉祥如意',
         '疏松透气的沙质土壤，泥炭:颗粒=3:7，忌积水',
         '7-10天','20天一次稀薄液肥','春季换盆好时机，逐步增加光照，新芽萌动期追肥',
         '5-7天','停止施肥','高温遮阴通风，忌烈日暴晒，25度以上半休眠控水',
         '7-10天','30天一次磷钾肥','增施磷钾促枝干木质化，减少氮肥防徒长',
         '15-20天','停止施肥','保暖5度以上入室，控水保微润，忌低温积水',
         '玉树以扦插繁殖为主，春秋季剪取健壮枝条晾干伤口后插于沙土，20天生根；叶插也可，取完整叶片平放于微润沙面',
         '2-3年换盆一次，春秋进行，修剪老根烂根，新土多加颗粒保透气，换盆后缓苗7-10天不浇水'),
        ('azalea', '杜鹃花', '🌺',
         '/images/azalea-cover.jpg',
         json.dumps(['/images/azalea-closeup.jpg', '/images/azalea-full.jpg', '/images/azalea-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '花开似锦，漫山红遍，中国传统名花',
         '喜酸性土壤，腐叶土+山泥+河沙(5:3:2)，忌碱性土',
         '3-5天','15天一次稀薄饼肥水','花后修剪残花，追施氮肥促新芽',
         '1-2天','薄肥少施','遮阴通风，忌烈日，早晚浇水，盆土保持湿润',
         '3-5天','20天一次磷钾肥','减少氮肥，增施磷钾促花芽分化',
         '5-7天','停止施肥','保暖5度以上，部分落叶品种可室外越冬，常绿品种入室',
         '扦插为主，5-6月选半木质化枝条插于酸性沙土，30天生根；也可高压繁殖',
         '2年换盆一次，花后进行，保留护心土，忌深栽'),
        ('osmanthus', '桂花', '🍂',
         '/images/osmanthus-cover.jpg',
         json.dumps(['/images/osmanthus-closeup.jpg', '/images/osmanthus-full.jpg', '/images/osmanthus-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '金秋飘香，十里芬芳，月宫仙树',
         '微酸性深厚壤土，腐叶土+园土+河沙(5:3:2)，忌积水',
         '3-5天','20天一次稀薄液肥','春梢萌发期追氮肥，修剪整形',
         '1-2天','15天一次磷钾肥','花期前增施磷钾促花，忌午间浇水',
         '3-5天','采花后追施一次复合肥','花后修剪残枝，施越冬基肥',
         '7-10天','停止施肥','北方入室保暖0度以上，少浇水',
         '嫁接为主，女贞或小叶女贞作砧木，春季靠接；扦插也可，6-7月进行',
         '3-4年换盆一次，春季进行，修剪老根，新盆加大排水层'),
        ('hyacinth', '风信子', '💙',
         '/images/hyacinth-cover.jpg',
         json.dumps(['/images/hyacinth-closeup.jpg', '/images/hyacinth-full.jpg', '/images/hyacinth-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '色彩缤纷，芬芳浓郁，春日信使',
         '疏松排水好的壤土，腐叶土+园土+河沙(4:4:2)，也可水培',
         '3-5天','10天一次稀薄液肥','花期营养生长期，保证充足阳光促花箭',
         '不需','花后停止施肥','夏季休眠，叶片枯黄后挖出鳞茎阴凉处存放',
         '种植后浇水','发芽后15天一次液肥','秋末种球，11月下种，冬季生根',
         '少量','不需','鳞茎在土中越冬萌芽，保持微润不积水',
          '分球繁殖为主，秋季分离侧球另行栽种；也可播种但需3-4年开花',
          '每年换盆换土，秋季种植时进行，鳞茎顶部露出土面1/3'),
        ('sun_rose', '太阳花', '🌤️',
         '/images/sun_rose-cover.jpg',
         json.dumps(['/images/sun_rose-closeup.jpg', '/images/sun_rose-full.jpg', '/images/sun_rose-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '向阳而生，花开灿烂，极易养护',
         '疏松排水好的沙质壤土，园土+河沙+腐叶土(3:4:3)，忌积水',
         '3-5天','15天一次稀薄液肥','春季播种或扦插，保证充足阳光促生长',
         '1-2天','不需','耐高温强光，夏季盛花期，见干见湿，忌积水烂根',
         '3-5天','每月一次磷钾肥','花后修剪残花，秋末减少浇水',
         '7-10天','停止施肥','不耐寒，10°C以下入室或作为一年生处理',
          '扦插极易成活，取5-8cm枝条插入沙土，7天生根；也可播种，春播为主',
          '每年春季换盆，根系浅用浅盆，排水层要厚'),
        ('money_tree', '发财树', '💰',
         '/images/money_tree-cover.jpg',
         json.dumps(['/images/money_tree-closeup.jpg', '/images/money_tree-full.jpg', '/images/money_tree-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '招财吉祥，四季常青，室内旺运',
         '疏松透气的微酸性土壤，腐叶土+园土+河沙(4:3:3)，忌积水',
         '7-10天','每月一次稀薄液肥','春季换盆修剪，逐步增加浇水量',
         '10-15天','不需','夏季生长缓慢忌浓肥，保持通风，避免烈日直射',
         '7-10天','每月一次复合肥','秋季减少浇水，增施磷钾肥增强抗性',
         '15-20天','停止施肥','保暖10°C以上，减少浇水，叶片喷水保润',
         '扦插繁殖，春夏取顶芽插入沙床，保持湿润30天生根；也可播种',
         '2年换盆一次，春季进行，修剪老根，盆底加厚排水层'),
        ('snake_plant', '虎皮兰', '🗡️',
         '/images/snake_plant-cover.jpg',
         json.dumps(['/images/snake_plant-closeup.jpg', '/images/snake_plant-full.jpg', '/images/snake_plant-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '挺拔刚劲，净化空气，懒人最爱',
         '疏松透气的沙质壤土，园土+河沙+腐叶土(3:4:3)，忌黏重积水',
         '7-10天','每月一次稀薄液肥','春暖增加光照，可分株繁殖',
         '10-15天','不需','耐旱耐阴，夏季庇荫，盆土干透再浇，忌积水',
         '7-10天','每月一次磷钾肥','秋季减少浇水，增加光照',
         '15-20天','停止施肥','耐阴耐旱，5°C以上可越冬，控水为主',
         '分株繁殖最简单，春季脱盆分切；叶插也可，取8cm叶段插入沙中',
         '2-3年换盆一次，春季进行，根系浅用浅盆，排水层要厚'),
        ('peperomia', '碧玉', '💚',
         '/images/peperomia-cover.jpg',
         json.dumps(['/images/peperomia-closeup.jpg', '/images/peperomia-full.jpg', '/images/peperomia-side.jpg']),
         json.dumps(['特写', '全株', '侧景']),
         '圆润可爱，碧绿如玉，桌面小清新',
         '疏松透气的腐殖土，腐叶土+河沙+珍珠岩(4:3:3)，忌积水',
         '5-7天','每月一次稀薄液肥','春季换盆修剪，分株扦插好时机',
         '3-5天','不需','夏季忌烈日直射，散射光为主，见干见湿',
         '5-7天','每月一次复合肥','秋季减少浇水，适当增加光照',
         '7-10天','停止施肥','保暖10°C以上，控水保微润，叶面可喷水',
         '叶插为主，取健康叶片带叶柄插入沙中，20天生根；也可分株或茎插',
         '每年春季换盆，浅盆为佳，保留护心土，排水要好'),
    ]

    for f in flowers:
        db.execute('''INSERT OR IGNORE INTO flower_knowledge
            (flower_id, name, emoji, photo, photos, photo_labels, `desc`, soil,
             spring_water, spring_fertilize, spring_tips,
             summer_water, summer_fertilize, summer_tips,
             autumn_water, autumn_fertilize, autumn_tips,
             winter_water, winter_fertilize, winter_tips,
             grafting, repot)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', f)
    db.commit()

def init_knowledge_topics(db):
    """插入通用知识专题"""
    topics = [
        ('soil', '🪴 营养土制作', '通用营养土配方、腐叶土制作、常见基质说明'),
        ('water', '💧 浇花水制作', '鸡蛋壳水、香蕉皮水、淘米水、果皮酵素、硫酸亚铁水、啤酒浇花'),
        ('grafting', '✂️ 嫁接技术', '劈接法、芽接法、靠接法、嫁接时机与注意事项'),
        ('fertilize', '🧪 施肥指南', '有机肥、化学肥分类、施肥原则、四季施肥要点'),
        ('pest', '🐛 病虫害防治', '蚜虫、红蜘蛛、介壳虫、小黑飞、黑斑病、白粉病、根腐病'),
        ('repot', '🔄 换盆换土', '换盆时机、换盆步骤、注意事项'),
    ]
    for t in topics:
        db.execute('INSERT OR IGNORE INTO knowledge_topics (topic_id, title, content) VALUES (?,?,?)', t)
    db.commit()


# ==================== API ROUTES ====================

# Serve HTML
@app.route('/')
def index():
    return send_from_directory(os.path.dirname(HTML_PATH), 'flower-care.html')

# Serve local images
@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(os.path.join(WORK_DIR, 'images'), filename)

# ---------- Auth ----------
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    city = data.get('city', '').strip()
    if len(username) < 3:
        return jsonify({'error': '用户名至少3个字符'}), 400
    if len(password) < 6:
        return jsonify({'error': '密码至少6位'}), 400
    db = get_db()
    existing = db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()
    if existing:
        return jsonify({'error': '用户名已被注册'}), 400
    db.execute('INSERT INTO users (username, password, city) VALUES (?,?,?)',
               (username, password, city))
    db.commit()
    user = db.execute('SELECT id, username, city FROM users WHERE username=?', (username,)).fetchone()
    return jsonify({'user': dict(user)})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    db = get_db()
    user = db.execute('SELECT id, username, city, avatar, password FROM users WHERE username=?', (username,)).fetchone()
    if not user:
        return jsonify({'error': '用户不存在'}), 400
    if user['password'] != password:
        return jsonify({'error': '密码错误'}), 400
    return jsonify({'user': {'id': user['id'], 'username': user['username'], 'city': user['city'], 'avatar': user.get('avatar', '')}})

# ---------- User Profile ----------
@app.route('/api/user/<int:user_id>/profile', methods=['GET'])
def get_profile(user_id):
    db = get_db()
    user = db.execute('SELECT id, username, city, avatar FROM users WHERE id=?', (user_id,)).fetchone()
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    flower_count = db.execute('SELECT COUNT(*) FROM user_flowers WHERE user_id=?', (user_id,)).fetchone()[0]
    water_count = db.execute("SELECT COUNT(*) FROM care_logs WHERE user_id=? AND action='water'", (user_id,)).fetchone()[0]
    fertilize_count = db.execute("SELECT COUNT(*) FROM care_logs WHERE user_id=? AND action='fertilize'", (user_id,)).fetchone()[0]
    return jsonify({
        'user': dict(user),
        'stats': {'flowers': flower_count, 'water': water_count, 'fertilize': fertilize_count}
    })

@app.route('/api/user/<int:user_id>/profile', methods=['PUT'])
def update_profile(user_id):
    data = request.json
    city = data.get('city', '').strip()
    db = get_db()
    db.execute('UPDATE users SET city=? WHERE id=?', (city, user_id))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/user/<int:user_id>/password', methods=['PUT'])
def change_password(user_id):
    data = request.json
    old_pass = data.get('old_password', '')
    new_pass = data.get('new_password', '')
    db = get_db()
    user = db.execute('SELECT password FROM users WHERE id=?', (user_id,)).fetchone()
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    if user['password'] != old_pass:
        return jsonify({'error': '当前密码错误'}), 400
    if len(new_pass) < 6:
        return jsonify({'error': '新密码至少6位'}), 400
    db.execute('UPDATE users SET password=? WHERE id=?', (new_pass, user_id))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/user/<int:user_id>/flower-config', methods=['GET'])
def get_flower_config(user_id):
    """获取用户的花卉显示配置，返回所有花卉的可见性和排序"""
    db = get_db()
    # 获取所有花卉
    all_flowers = db.execute("SELECT flower_id, name, emoji FROM flower_knowledge ORDER BY id").fetchall()
    # 获取用户配置
    configs = db.execute("SELECT flower_id, visible, sort_order FROM user_flower_config WHERE user_id=?", (user_id,)).fetchall()
    config_map = {c['flower_id']: dict(c) for c in configs}

    result = []
    for idx, f in enumerate(all_flowers):
        cfg = config_map.get(f['flower_id'])
        result.append({
            'flower_id': f['flower_id'],
            'name': f['name'],
            'emoji': f['emoji'],
            'visible': cfg['visible'] if cfg else 1,
            'sort_order': cfg['sort_order'] if cfg else idx,
        })
    # 按 sort_order 排序
    result.sort(key=lambda x: x['sort_order'])
    return jsonify({'config': result})

@app.route('/api/user/<int:user_id>/flower-config', methods=['PUT'])
def update_flower_config(user_id):
    """批量更新用户的花卉显示配置"""
    data = request.json
    items = data.get('items', [])
    db = get_db()
    for item in items:
        flower_id = item.get('flower_id')
        visible = item.get('visible', 1)
        sort_order = item.get('sort_order', 0)
        db.execute('''INSERT INTO user_flower_config (user_id, flower_id, visible, sort_order)
                      VALUES (?, ?, ?, ?)
                      ON CONFLICT(user_id, flower_id) DO UPDATE SET visible=excluded.visible, sort_order=excluded.sort_order''',
                   (user_id, flower_id, visible, sort_order))
    db.commit()
    return jsonify({'success': True})

# ---------- Flower Knowledge (public) ----------
@app.route('/api/flowers', methods=['GET'])
def get_flowers():
    """获取花卉列表，支持模糊查询和用户配置过滤排序"""
    search = request.args.get('search', '').strip()
    user_id = request.args.get('user_id', '')
    db = get_db()
    if search:
        rows = db.execute(
            "SELECT * FROM flower_knowledge WHERE name LIKE ? OR flower_id LIKE ? OR `desc` LIKE ?",
            (f'%{search}%', f'%{search}%', f'%{search}%')
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM flower_knowledge ORDER BY id").fetchall()

    # 获取用户配置（如果提供了 user_id）
    config_map = {}
    if user_id:
        try:
            uid = int(user_id)
            configs = db.execute("SELECT flower_id, visible, sort_order FROM user_flower_config WHERE user_id=?", (uid,)).fetchall()
            config_map = {c['flower_id']: dict(c) for c in configs}
        except (ValueError, TypeError):
            pass

    result = []
    for r in rows:
        item = dict(r)
        item['photos'] = json.loads(item['photos']) if item['photos'] else []
        item['photo_labels'] = json.loads(item['photo_labels']) if item['photo_labels'] else []
        # Build seasons structure
        item['seasons'] = {
            'spring': {'water': item.pop('spring_water',''), 'fertilize': item.pop('spring_fertilize',''), 'tips': item.pop('spring_tips','')},
            'summer': {'water': item.pop('summer_water',''), 'fertilize': item.pop('summer_fertilize',''), 'tips': item.pop('summer_tips','')},
            'autumn': {'water': item.pop('autumn_water',''), 'fertilize': item.pop('autumn_fertilize',''), 'tips': item.pop('autumn_tips','')},
            'winter': {'water': item.pop('winter_water',''), 'fertilize': item.pop('winter_fertilize',''), 'tips': item.pop('winter_tips','')}
        }
        # 应用用户配置
        cfg = config_map.get(item['flower_id'])
        item['visible'] = cfg['visible'] if cfg else 1
        item['sort_order'] = cfg['sort_order'] if cfg else 0
        result.append(item)

    # 按用户配置排序
    if config_map:
        result.sort(key=lambda x: x.get('sort_order', 0))
        # 过滤不可见的花卉
        result = [f for f in result if f.get('visible', 1) == 1]

    return jsonify({'flowers': result})

@app.route('/api/flowers/<flower_id>', methods=['GET'])
def get_flower_detail(flower_id):
    """获取单个花卉详情，支持city参数返回气候调整数据"""
    db = get_db()
    r = db.execute("SELECT * FROM flower_knowledge WHERE flower_id=?", (flower_id,)).fetchone()
    if not r:
        return jsonify({'error': '花卉不存在'}), 404
    item = dict(r)
    item['photos'] = json.loads(item['photos']) if item['photos'] else []
    item['photo_labels'] = json.loads(item['photo_labels']) if item['photo_labels'] else []

    city = request.args.get('city', '').strip()
    zone_id = None
    if city:
        zone_id, _ = get_climate_zone(city)

    seasons = {}
    for s in ('spring', 'summer', 'autumn', 'winter'):
        if zone_id:
            adj = get_adjusted_season_care(item, zone_id, s)
            seasons[s] = {
                'water': adj['water'],
                'fertilize': adj['fertilize'],
                'tips': adj['tips'],
                'water_original': adj['water_original'],
                'fertilize_original': adj['fertilize_original'],
            }
        else:
            seasons[s] = {
                'water': item.pop(f'{s}_water', ''),
                'fertilize': item.pop(f'{s}_fertilize', ''),
                'tips': item.pop(f'{s}_tips', ''),
            }
        # Remove raw DB columns
        for col in (f'{s}_water', f'{s}_fertilize', f'{s}_tips'):
            item.pop(col, None)

    item['seasons'] = seasons
    if zone_id:
        item['climate_zone'] = CLIMATE_ZONES[zone_id]['name']
    return jsonify(item)

# ---------- Knowledge Topics ----------
@app.route('/api/knowledge-topics', methods=['GET'])
def get_knowledge_topics():
    db = get_db()
    rows = db.execute("SELECT topic_id, title, content FROM knowledge_topics ORDER BY id").fetchall()
    return jsonify({'topics': [dict(r) for r in rows]})

# ---------- Flower Order (Drag & Drop) ----------
@app.route('/api/user/<int:user_id>/flower-order', methods=['GET'])
def get_flower_order(user_id):
    db = get_db()
    row = db.execute('SELECT flower_order FROM user_flower_orders WHERE user_id=?', (user_id,)).fetchone()
    order = json.loads(row['flower_order']) if row else []
    return jsonify({'order': order})

@app.route('/api/user/<int:user_id>/flower-order', methods=['PUT'])
def save_flower_order(user_id):
    data = request.json
    order = data.get('order', [])
    if not isinstance(order, list):
        return jsonify({'error': '无效排序数据'}), 400
    db = get_db()
    db.execute('INSERT OR REPLACE INTO user_flower_orders (user_id, flower_order) VALUES (?, ?)',
               (user_id, json.dumps(order)))
    db.commit()
    return jsonify({'success': True})

# ---------- User Flowers ----------
@app.route('/api/user/<int:user_id>/flowers', methods=['GET'])
def get_user_flowers(user_id):
    db = get_db()
    # Get user city for climate adjustment
    user = db.execute('SELECT city FROM users WHERE id=?', (user_id,)).fetchone()
    city = user['city'] if user else ''
    zone_id, _ = get_climate_zone(city) if city else ('warm_temp', CLIMATE_ZONES['warm_temp'])

    rows = db.execute('''
        SELECT uf.flower_id, uf.added_at, uf.last_water, uf.last_fertilize, uf.last_repot,
               fk.name, fk.emoji, fk.photo,
               fk.spring_water, fk.spring_fertilize, fk.spring_tips,
               fk.summer_water, fk.summer_fertilize, fk.summer_tips,
               fk.autumn_water, fk.autumn_fertilize, fk.autumn_tips,
               fk.winter_water, fk.winter_fertilize, fk.winter_tips
        FROM user_flowers uf
        JOIN flower_knowledge fk ON uf.flower_id = fk.flower_id
        WHERE uf.user_id=?
        ORDER BY uf.added_at
    ''', (user_id,)).fetchall()
    result = []
    for r in rows:
        item = dict(r)
        seasons = {}
        for s in ('spring', 'summer', 'autumn', 'winter'):
            adj = get_adjusted_season_care(item, zone_id, s)
            seasons[s] = {
                'water': adj['water'],
                'fertilize': adj['fertilize'],
                'tips': adj['tips'],
                'water_original': adj['water_original'],
                'fertilize_original': adj['fertilize_original'],
            }
            # Remove raw DB columns
            for col in (f'{s}_water', f'{s}_fertilize', f'{s}_tips'):
                item.pop(col, None)
        item['seasons'] = seasons
        result.append(item)
    # Include climate info
    zone_info = CLIMATE_ZONES[zone_id]
    return jsonify({
        'flowers': result,
        'climate': {
            'city': city,
            'zone_id': zone_id,
            'zone_name': zone_info['name'],
            'zone_desc': zone_info['desc'],
        }
    })

@app.route('/api/user/<int:user_id>/flowers/<flower_id>', methods=['POST'])
def add_user_flower(user_id, flower_id):
    db = get_db()
    try:
        db.execute('INSERT INTO user_flowers (user_id, flower_id) VALUES (?,?)', (user_id, flower_id))
        db.commit()
        return jsonify({'success': True})
    except Exception:
        return jsonify({'error': '已添加过该花卉'}), 400

@app.route('/api/user/<int:user_id>/flowers/<flower_id>', methods=['DELETE'])
def remove_user_flower(user_id, flower_id):
    db = get_db()
    db.execute('DELETE FROM user_flowers WHERE user_id=? AND flower_id=?', (user_id, flower_id))
    db.execute('DELETE FROM care_logs WHERE user_id=? AND flower_id=?', (user_id, flower_id))
    db.commit()
    return jsonify({'success': True})

# ---------- Care Actions ----------
@app.route('/api/user/<int:user_id>/care', methods=['POST'])
def record_care(user_id):
    data = request.json
    flower_id = data.get('flower_id')
    action = data.get('action')  # water / fertilize / repot
    if action not in ('water', 'fertilize', 'repot'):
        return jsonify({'error': '无效操作'}), 400
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db = get_db()
    # Update last_action in user_flowers
    col = f'last_{action}'
    db.execute(f'UPDATE user_flowers SET {col}=? WHERE user_id=? AND flower_id=?',
               (now, user_id, flower_id))
    # Add log
    db.execute('INSERT INTO care_logs (user_id, flower_id, action, date) VALUES (?,?,?,?)',
               (user_id, flower_id, action, now))
    db.commit()
    return jsonify({'success': True, 'date': now})

@app.route('/api/user/<int:user_id>/care-logs', methods=['GET'])
def get_care_logs(user_id):
    flower_id = request.args.get('flower_id')
    db = get_db()
    if flower_id:
        rows = db.execute('SELECT * FROM care_logs WHERE user_id=? AND flower_id=? ORDER BY date DESC LIMIT 50',
                          (user_id, flower_id)).fetchall()
    else:
        rows = db.execute('SELECT * FROM care_logs WHERE user_id=? ORDER BY date DESC LIMIT 100',
                          (user_id,)).fetchall()
    return jsonify({'logs': [dict(r) for r in rows]})

# ---------- Reminders ----------
@app.route('/api/user/<int:user_id>/reminders', methods=['GET'])
def get_reminders(user_id):
    """基于植株浇水计划的提醒：提前2/1/0天提醒，过期每日提醒，支持确认/保持"""
    db = get_db()
    today = datetime.now().strftime('%Y-%m-%d')
    today_dt = datetime.now().date()

    reminders = []

    # 获取用户所有植株及其下一个 pending 的浇水计划
    plants = db.execute('''
        SELECT mp.id as plant_id, mp.plant_name, mp.photo as plant_photo,
               mp.flower_id, fk.name as flower_name, fk.emoji, fk.photo
        FROM my_plants mp
        JOIN flower_knowledge fk ON mp.flower_id = fk.flower_id
        WHERE mp.user_id=?
        ORDER BY mp.created_at
    ''', (user_id,)).fetchall()

    for p in plants:
        # 找到该植株最近的一个 pending 计划
        next_plan = db.execute('''
            SELECT id, plan_date, status, reminder_status, reminder_updated
            FROM water_plans
            WHERE plant_id=? AND status='pending'
            ORDER BY plan_date ASC
            LIMIT 1
        ''', (p['plant_id'],)).fetchone()

        if not next_plan:
            continue

        plan_date = datetime.strptime(next_plan['plan_date'], '%Y-%m-%d').date()
        days_until = (plan_date - today_dt).days
        reminder_status = next_plan['reminder_status'] or 'pending'

        # 如果已确认，跳过该提醒（本周期不再提醒）
        if reminder_status == 'confirmed':
            continue

        # 构建提醒信息
        plant_display = p['plant_name'] or p['flower_name']
        item = {
            'plant_id': p['plant_id'],
            'plan_id': next_plan['id'],
            'flower_id': p['flower_id'],
            'name': plant_display,
            'emoji': p['emoji'],
            'plant_photo': p['plant_photo'],
            'flower_photo': p['photo'],
            'type': 'water',
            'plan_date': next_plan['plan_date'],
            'reminder_status': reminder_status,
        }

        if days_until < 0:
            item['status'] = 'overdue'
            item['msg'] = f'已超过浇水日期{abs(days_until)}天'
            item['days'] = abs(days_until)
        elif days_until == 0:
            item['status'] = 'today'
            item['msg'] = '今天需要浇水'
            item['days'] = 0
        elif days_until == 1:
            item['status'] = 'soon'
            item['msg'] = '明天需要浇水'
            item['days'] = 1
        elif days_until == 2:
            item['status'] = 'soon'
            item['msg'] = '后天需要浇水'
            item['days'] = 2
        else:
            # 还早，不显示提醒
            continue

        reminders.append(item)

    # 保留花卉级施肥提醒（基于 user_flowers 表）
    user = db.execute('SELECT city FROM users WHERE id=?', (user_id,)).fetchone()
    city = user['city'] if user else ''
    zone_id, _ = get_climate_zone(city) if city else ('warm_temp', CLIMATE_ZONES['warm_temp'])

    flower_rows = db.execute('''
        SELECT uf.flower_id, uf.last_fertilize,
               fk.name, fk.emoji,
               fk.spring_fertilize, fk.summer_fertilize, fk.autumn_fertilize, fk.winter_fertilize
        FROM user_flowers uf
        JOIN flower_knowledge fk ON uf.flower_id = fk.flower_id
        WHERE uf.user_id=?
    ''', (user_id,)).fetchall()

    now = datetime.now()
    for r in flower_rows:
        item = dict(r)
        month = now.month
        if month in (3,4,5): season = 'spring'
        elif month in (6,7,8): season = 'summer'
        elif month in (9,10,11): season = 'autumn'
        else: season = 'winter'

        adj_care = get_adjusted_season_care(item, zone_id, season)
        fert_interval_str = adj_care['fertilize']

        if '停' in fert_interval_str or '不需' in fert_interval_str:
            continue
        fm = re_match(fert_interval_str)
        if not fm:
            continue

        fert_interval = fm
        if item['last_fertilize']:
            last = datetime.strptime(item['last_fertilize'], '%Y-%m-%d %H:%M:%S')
            days_since = (now - last).days
            remaining = fert_interval - days_since
            if remaining <= 0:
                reminders.append({'flower_id': item['flower_id'], 'name': item['name'], 'emoji': item['emoji'],
                                  'type': 'fertilize', 'status': 'overdue', 'msg': f'已超过施肥周期{abs(remaining)}天', 'days': days_since,
                                  'plant_id': None, 'plan_id': None, 'reminder_status': None})
            elif remaining == 0:
                reminders.append({'flower_id': item['flower_id'], 'name': item['name'], 'emoji': item['emoji'],
                                  'type': 'fertilize', 'status': 'today', 'msg': '今天需要施肥', 'days': days_since,
                                  'plant_id': None, 'plan_id': None, 'reminder_status': None})
        else:
            reminders.append({'flower_id': item['flower_id'], 'name': item['name'], 'emoji': item['emoji'],
                              'type': 'fertilize', 'status': 'overdue', 'msg': '尚未记录施肥', 'days': None,
                              'plant_id': None, 'plan_id': None, 'reminder_status': None})

    # 排序：overdue + kept > overdue > today > soon
    def sort_key(x):
        status_order = {'overdue': 0, 'today': 1, 'soon': 2}
        kept_boost = -1 if x.get('reminder_status') == 'kept' else 0
        return (status_order.get(x['status'], 3) + kept_boost, x.get('days', 999))
    reminders.sort(key=sort_key)

    return jsonify({'reminders': reminders})

def re_match(s):
    """Extract first number from string like '3-5天' or '7天'"""
    import re
    m = re.search(r'(\d+)', s)
    if m:
        nums = re.findall(r'\d+', s)
        if len(nums) >= 2:
            return round((int(nums[0]) + int(nums[1])) / 2)
        return int(nums[0])
    return None

def re_match_range(s):
    """Extract min and max days from string like '3-5天' or '7天', returns (min, max)"""
    import re
    nums = re.findall(r'\d+', s)
    if len(nums) >= 2:
        return int(nums[0]), int(nums[1])
    elif len(nums) == 1:
        return int(nums[0]), int(nums[0])
    return None, None

# ==================== MY PLANTS (植株管理) ====================

@app.route('/api/user/<int:user_id>/plants', methods=['GET'])
def get_plants(user_id):
    """获取用户所有植株，可按flower_id过滤"""
    db = get_db()
    flower_id = request.args.get('flower_id', '').strip()
    user = db.execute('SELECT city FROM users WHERE id=?', (user_id,)).fetchone()
    city = user['city'] if user else ''
    zone_id, _ = get_climate_zone(city) if city else ('warm_temp', CLIMATE_ZONES['warm_temp'])

    if flower_id:
        rows = db.execute('''
            SELECT mp.id, mp.flower_id, mp.plant_name, mp.custom_water_days, mp.photo, mp.identify_result, mp.created_at,
                   fk.name as flower_name, fk.emoji, fk.photo
            FROM my_plants mp
            JOIN flower_knowledge fk ON mp.flower_id = fk.flower_id
            WHERE mp.user_id=? AND mp.flower_id=?
            ORDER BY mp.created_at
        ''', (user_id, flower_id)).fetchall()
    else:
        rows = db.execute('''
            SELECT mp.id, mp.flower_id, mp.plant_name, mp.custom_water_days, mp.photo, mp.identify_result, mp.created_at,
                   fk.name as flower_name, fk.emoji, fk.photo
            FROM my_plants mp
            JOIN flower_knowledge fk ON mp.flower_id = fk.flower_id
            WHERE mp.user_id=?
            ORDER BY mp.created_at
        ''', (user_id,)).fetchall()

    result = []
    for r in rows:
        item = dict(r)
        # Parse identify_result JSON if present
        if item.get('identify_result'):
            try:
                item['identify_result'] = json.loads(item['identify_result'])
            except Exception:
                item['identify_result'] = None
        else:
            item['identify_result'] = None
        # Get current season and adjusted water interval
        now = datetime.now()
        month = now.month
        if month in (3,4,5): season = 'spring'
        elif month in (6,7,8): season = 'summer'
        elif month in (9,10,11): season = 'autumn'
        else: season = 'winter'

        fk = db.execute('''SELECT spring_water, summer_water, autumn_water, winter_water
                           FROM flower_knowledge WHERE flower_id=?''', (r['flower_id'],)).fetchone()
        if fk:
            adj = get_adjusted_season_care(dict(fk), zone_id, season)
            item['water_interval'] = adj['water']
            item['water_interval_original'] = adj.get('water_original', adj['water'])
            item['current_season'] = season
            # If custom_water_days is set, use it as the effective interval
            cwd = r['custom_water_days']
            item['custom_water_days'] = cwd
            if cwd:
                item['water_interval_effective'] = f'{cwd}天'
            else:
                item['water_interval_effective'] = adj['water']
        result.append(item)
    return jsonify({'plants': result})

@app.route('/api/user/<int:user_id>/plants', methods=['POST'])
def add_plant(user_id):
    """添加植株，自动生成未来浇水计划"""
    data = request.json
    flower_id = data.get('flower_id', '').strip()
    plant_name = data.get('plant_name', '').strip()
    if not flower_id or not plant_name:
        return jsonify({'error': '请填写花卉类型和植株名称'}), 400
    if len(plant_name) > 20:
        return jsonify({'error': '植株名称不能超过20个字符'}), 400

    db = get_db()
    # Verify flower exists
    fk = db.execute('SELECT flower_id FROM flower_knowledge WHERE flower_id=?', (flower_id,)).fetchone()
    if not fk:
        return jsonify({'error': '花卉不存在'}), 404

    # Get user city for climate adjustment
    user = db.execute('SELECT city FROM users WHERE id=?', (user_id,)).fetchone()
    city = user['city'] if user else ''
    zone_id, _ = get_climate_zone(city) if city else ('warm_temp', CLIMATE_ZONES['warm_temp'])

    # Create plant
    cursor = db.execute('INSERT INTO my_plants (user_id, flower_id, plant_name) VALUES (?,?,?)',
                        (user_id, flower_id, plant_name))
    plant_id = cursor.lastrowid

    # Auto-generate watering plan for next 30 days
    _generate_water_plans(db, plant_id, user_id, flower_id, zone_id)

    db.commit()

    plant = db.execute('SELECT id, flower_id, plant_name, created_at FROM my_plants WHERE id=?', (plant_id,)).fetchone()
    return jsonify({'success': True, 'plant': dict(plant)})

@app.route('/api/user/<int:user_id>/plants/<int:plant_id>', methods=['PUT'])
def update_plant(user_id, plant_id):
    """修改植株名称和/或自定义浇水周期"""
    data = request.json
    db = get_db()
    plant = db.execute('SELECT id FROM my_plants WHERE id=? AND user_id=?', (plant_id, user_id)).fetchone()
    if not plant:
        return jsonify({'error': '植株不存在'}), 404

    updates = []
    params = []
    if 'plant_name' in data:
        plant_name = data['plant_name'].strip()
        if not plant_name or len(plant_name) > 20:
            return jsonify({'error': '植株名称不能为空且不超过20字'}), 400
        updates.append('plant_name=?')
        params.append(plant_name)
    if 'custom_water_days' in data:
        val = data['custom_water_days']
        if val is not None:
            val = int(val)
            if val < 1 or val > 60:
                return jsonify({'error': '浇水周期需在1-60天之间'}), 400
        updates.append('custom_water_days=?')
        params.append(val)

    if not updates:
        return jsonify({'error': '无更新内容'}), 400

    params.extend([plant_id, user_id])
    db.execute(f'UPDATE my_plants SET {",".join(updates)} WHERE id=? AND user_id=?', params)
    db.commit()

    # If custom_water_days changed, regenerate pending water plans
    if 'custom_water_days' in data:
        db.execute('DELETE FROM water_plans WHERE plant_id=? AND status=?', (plant_id, 'pending'))
        user = db.execute('SELECT city FROM users WHERE id=?', (user_id,)).fetchone()
        city = user['city'] if user else ''
        zone_id, _ = get_climate_zone(city) if city else ('warm_temp', CLIMATE_ZONES['warm_temp'])
        plant_row = db.execute('SELECT flower_id FROM my_plants WHERE id=?', (plant_id,)).fetchone()
        if plant_row:
            _generate_water_plans(db, plant_id, user_id, plant_row['flower_id'], zone_id)
        db.commit()

    return jsonify({'success': True})

@app.route('/api/user/<int:user_id>/plants/<int:plant_id>', methods=['DELETE'])
def delete_plant(user_id, plant_id):
    """删除植株及其浇水计划"""
    db = get_db()
    db.execute('DELETE FROM water_plans WHERE plant_id=?', (plant_id,))
    db.execute('DELETE FROM my_plants WHERE id=? AND user_id=?', (plant_id, user_id))
    db.commit()
    return jsonify({'success': True})

def _generate_water_plans(db, plant_id, user_id, flower_id, zone_id):
    """为植株生成未来浇水计划（从今天开始的后续plan）"""
    from datetime import timedelta

    # Check if plant has custom_water_days
    plant_row = db.execute('SELECT custom_water_days FROM my_plants WHERE id=?', (plant_id,)).fetchone()
    custom_days = plant_row['custom_water_days'] if plant_row else None

    fk_row = db.execute('''SELECT spring_water, summer_water, autumn_water, winter_water
                           FROM flower_knowledge WHERE flower_id=?''', (flower_id,)).fetchone()
    if not fk_row:
        return

    now = datetime.now()
    # Determine how many plans already exist for this plant
    existing = db.execute('SELECT MAX(plan_date) FROM water_plans WHERE plant_id=?', (plant_id,)).fetchone()[0]
    start_date = now
    if existing:
        last_plan = datetime.strptime(existing, '%Y-%m-%d')
        if last_plan > start_date:
            start_date = last_plan

    # Generate plans for next 90 days from start_date
    current = start_date
    end_horizon = now + timedelta(days=90)

    while current < end_horizon:
        if custom_days:
            # Use custom interval - fixed days regardless of season
            interval = custom_days
            next_date = current + timedelta(days=interval)
        else:
            month = current.month
            if month in (3,4,5): season = 'spring'
            elif month in (6,7,8): season = 'summer'
            elif month in (9,10,11): season = 'autumn'
            else: season = 'winter'

            adj = get_adjusted_season_care(dict(fk_row), zone_id, season)
            water_str = adj['water']

            # Skip if no watering needed
            if '停' in water_str or '不需' in water_str:
                current = current + timedelta(days=30)
                continue

            lo, hi = re_match_range(water_str)
            if lo is None:
                current = current + timedelta(days=7)
                continue

            interval = round((lo + hi) / 2)
            next_date = current + timedelta(days=interval)

        # Check if plan already exists for this date
        plan_date_str = next_date.strftime('%Y-%m-%d')
        exists = db.execute('SELECT id FROM water_plans WHERE plant_id=? AND plan_date=?', (plant_id, plan_date_str)).fetchone()
        if not exists:
            db.execute('INSERT INTO water_plans (plant_id, plan_date, status) VALUES (?,?,?)',
                       (plant_id, plan_date_str, 'pending'))
        current = next_date

# ==================== WATER PLANS (浇水计划) ====================

@app.route('/api/user/<int:user_id>/plants/<int:plant_id>/water-plans', methods=['GET'])
def get_water_plans(user_id, plant_id):
    """获取某植株的浇水计划"""
    db = get_db()
    # Verify plant belongs to user
    plant = db.execute('SELECT id FROM my_plants WHERE id=? AND user_id=?', (plant_id, user_id)).fetchone()
    if not plant:
        return jsonify({'error': '植株不存在'}), 404

    status_filter = request.args.get('status', '').strip()  # pending / done / skipped

    if status_filter:
        rows = db.execute('''
            SELECT id, plan_date, status, actual_date, notes, created_at, reminder_status, reminder_updated
            FROM water_plans WHERE plant_id=? AND status=?
            ORDER BY plan_date
        ''', (plant_id, status_filter)).fetchall()
    else:
        rows = db.execute('''
            SELECT id, plan_date, status, actual_date, notes, created_at, reminder_status, reminder_updated
            FROM water_plans WHERE plant_id=?
            ORDER BY plan_date
        ''', (plant_id,)).fetchall()

    return jsonify({'plans': [dict(r) for r in rows]})

@app.route('/api/user/<int:user_id>/water-plans/<int:plan_id>/complete', methods=['POST'])
def complete_water_plan(user_id, plan_id):
    """完成浇水（标记计划为已完成），并更新下次计划"""
    db = get_db()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    plan = db.execute('''
        SELECT wp.id, wp.plant_id, wp.plan_date, wp.status, mp.flower_id, mp.user_id
        FROM water_plans wp JOIN my_plants mp ON wp.plant_id = mp.id
        WHERE wp.id=? AND mp.user_id=?
    ''', (plan_id, user_id)).fetchone()
    if not plan:
        return jsonify({'error': '计划不存在'}), 404

    db.execute('UPDATE water_plans SET status=?, actual_date=? WHERE id=?', ('done', now_str, plan_id))

    # Generate more future plans if needed
    user = db.execute('SELECT city FROM users WHERE id=?', (user_id,)).fetchone()
    city = user['city'] if user else ''
    zone_id, _ = get_climate_zone(city) if city else ('warm_temp', CLIMATE_ZONES['warm_temp'])
    _generate_water_plans(db, plan['plant_id'], user_id, plan['flower_id'], zone_id)

    db.commit()
    return jsonify({'success': True, 'actual_date': now_str})

@app.route('/api/user/<int:user_id>/water-plans/<int:plan_id>/skip', methods=['POST'])
def skip_water_plan(user_id, plan_id):
    """跳过浇水"""
    db = get_db()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    plan = db.execute('''
        SELECT wp.id, wp.plant_id, mp.user_id
        FROM water_plans wp JOIN my_plants mp ON wp.plant_id = mp.id
        WHERE wp.id=? AND mp.user_id=?
    ''', (plan_id, user_id)).fetchone()
    if not plan:
        return jsonify({'error': '计划不存在'}), 404

    db.execute('UPDATE water_plans SET status=?, actual_date=? WHERE id=?', ('skipped', now_str, plan_id))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/user/<int:user_id>/water-plans/<int:plan_id>/confirm', methods=['POST'])
def confirm_water_plan(user_id, plan_id):
    """确认浇水提醒：本周期不再提醒"""
    db = get_db()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    plan = db.execute('''
        SELECT wp.id, wp.plant_id, mp.user_id
        FROM water_plans wp JOIN my_plants mp ON wp.plant_id = mp.id
        WHERE wp.id=? AND mp.user_id=?
    ''', (plan_id, user_id)).fetchone()
    if not plan:
        return jsonify({'error': '计划不存在'}), 404

    db.execute('UPDATE water_plans SET reminder_status=?, reminder_updated=? WHERE id=?',
               ('confirmed', now_str, plan_id))
    db.commit()
    return jsonify({'success': True, 'reminder_status': 'confirmed'})

@app.route('/api/user/<int:user_id>/water-plans/<int:plan_id>/keep', methods=['POST'])
def keep_water_plan(user_id, plan_id):
    """保持提醒：继续显示该提醒"""
    db = get_db()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    plan = db.execute('''
        SELECT wp.id, wp.plant_id, mp.user_id
        FROM water_plans wp JOIN my_plants mp ON wp.plant_id = mp.id
        WHERE wp.id=? AND mp.user_id=?
    ''', (plan_id, user_id)).fetchone()
    if not plan:
        return jsonify({'error': '计划不存在'}), 404

    db.execute('UPDATE water_plans SET reminder_status=?, reminder_updated=? WHERE id=?',
               ('kept', now_str, plan_id))
    db.commit()
    return jsonify({'success': True, 'reminder_status': 'kept'})

@app.route('/api/user/<int:user_id>/plants/<int:plant_id>/water-plans/regenerate', methods=['POST'])
def regenerate_water_plans(user_id, plant_id):
    """重新生成浇水计划（清除pending的计划，重新计算）"""
    db = get_db()
    plant = db.execute('SELECT id, flower_id FROM my_plants WHERE id=? AND user_id=?', (plant_id, user_id)).fetchone()
    if not plant:
        return jsonify({'error': '植株不存在'}), 404

    # Delete pending plans only (keep done/skipped as history)
    db.execute('DELETE FROM water_plans WHERE plant_id=? AND status=?', (plant_id, 'pending'))

    user = db.execute('SELECT city FROM users WHERE id=?', (user_id,)).fetchone()
    city = user['city'] if user else ''
    zone_id, _ = get_climate_zone(city) if city else ('warm_temp', CLIMATE_ZONES['warm_temp'])
    _generate_water_plans(db, plant_id, user_id, plant['flower_id'], zone_id)

    db.commit()
    return jsonify({'success': True})

@app.route('/api/user/<int:user_id>/water-summary', methods=['GET'])
def get_water_summary(user_id):
    """获取用户所有植株的浇水汇总"""
    db = get_db()
    user = db.execute('SELECT city FROM users WHERE id=?', (user_id,)).fetchone()
    city = user['city'] if user else ''
    zone_id, _ = get_climate_zone(city) if city else ('warm_temp', CLIMATE_ZONES['warm_temp'])

    plants = db.execute('''
        SELECT mp.id, mp.flower_id, mp.plant_name, fk.name as flower_name, fk.emoji, fk.photo
        FROM my_plants mp
        JOIN flower_knowledge fk ON mp.flower_id = fk.flower_id
        WHERE mp.user_id=?
        ORDER BY mp.created_at
    ''', (user_id,)).fetchall()

    today = datetime.now().strftime('%Y-%m-%d')
    result = []
    for p in plants:
        # Pending count
        pending = db.execute('''
            SELECT COUNT(*) FROM water_plans WHERE plant_id=? AND status='pending' AND plan_date <= ?
        ''', (p['id'], today)).fetchone()[0]

        # Next plan
        next_plan = db.execute('''
            SELECT id, plan_date, status FROM water_plans
            WHERE plant_id=? AND status='pending' AND plan_date >= ?
            ORDER BY plan_date LIMIT 1
        ''', (p['id'], today)).fetchone()

        # Recent done count (last 30 days)
        done_count = db.execute('''
            SELECT COUNT(*) FROM water_plans
            WHERE plant_id=? AND status='done' AND actual_date >= date('now', '-30 days')
        ''', (p['id'],)).fetchone()[0]

        item = dict(p)
        item['overdue_count'] = pending
        item['next_plan'] = dict(next_plan) if next_plan else None
        item['done_count_30d'] = done_count

        # Today's plans
        today_plans = db.execute('''
            SELECT id, plan_date, status FROM water_plans
            WHERE plant_id=? AND plan_date = ? AND status='pending'
        ''', (p['id'], today)).fetchall()
        item['today_plans'] = [dict(tp) for tp in today_plans]

        result.append(item)

    return jsonify({'summary': result})


# ==================== CLIMATE ZONE SYSTEM ====================
# 气候带定义：
#   tropical     热带      全年高温多雨，无冬季
#   subtropical  亚热带    夏热冬温，四季分明，梅雨季
#   warm_temp    暖温带    夏热冬冷，四季分明，干燥
#   mid_temp     中温带    夏暖冬寒，生长季短
#   cold_temp    寒温带    夏短冬长，严寒
#   plateau      高原气候  日照强温差大，紫外线强
#   arid         干旱半干旱 蒸发量大，降水少

CLIMATE_ZONES = {
    'tropical': {
        'name': '热带',
        'desc': '全年高温多雨，冬季温暖，植物几乎不休眠',
        'adjust': {
            'water':   {'spring': 0.7, 'summer': 0.8, 'autumn': 0.7, 'winter': 0.6},
            'fertilize':{'spring': 0.85, 'summer': 0.85, 'autumn': 0.85, 'winter': 0.8},
            'repot_offset': -1,   # 比标准早1个月
            'graft_offset': -1,
        }
    },
    'subtropical': {
        'name': '亚热带',
        'desc': '夏热冬温，四季分明，梅雨季湿度大',
        'adjust': {
            'water':   {'spring': 0.85, 'summer': 0.8, 'autumn': 0.85, 'winter': 0.85},
            'fertilize':{'spring': 0.9, 'summer': 0.9, 'autumn': 0.9, 'winter': 0.9},
            'repot_offset': 0,
            'graft_offset': 0,
        }
    },
    'warm_temp': {
        'name': '暖温带',
        'desc': '夏热冬冷，四季分明，空气较干燥',
        'adjust': {
            'water':   {'spring': 1.0, 'summer': 1.0, 'autumn': 1.0, 'winter': 1.0},
            'fertilize':{'spring': 1.0, 'summer': 1.0, 'autumn': 1.0, 'winter': 1.0},
            'repot_offset': 0,
            'graft_offset': 0,
        }
    },
    'mid_temp': {
        'name': '中温带',
        'desc': '夏暖冬寒，生长季较短，需注意越冬',
        'adjust': {
            'water':   {'spring': 1.15, 'summer': 1.1, 'autumn': 1.15, 'winter': 1.2},
            'fertilize':{'spring': 1.1, 'summer': 1.05, 'autumn': 1.1, 'winter': 1.2},
            'repot_offset': 1,   # 比标准晚1个月
            'graft_offset': 1,
        }
    },
    'cold_temp': {
        'name': '寒温带',
        'desc': '夏短冬长严寒，生长季很短，大部分花需室内越冬',
        'adjust': {
            'water':   {'spring': 1.25, 'summer': 1.2, 'autumn': 1.3, 'winter': 1.4},
            'fertilize':{'spring': 1.2, 'summer': 1.15, 'autumn': 1.25, 'winter': 1.4},
            'repot_offset': 2,
            'graft_offset': 2,
        }
    },
    'plateau': {
        'name': '高原气候',
        'desc': '日照强温差大，紫外线强，蒸发快，需注意防晒保湿',
        'adjust': {
            'water':   {'spring': 0.8, 'summer': 0.75, 'autumn': 0.8, 'winter': 0.9},
            'fertilize':{'spring': 0.9, 'summer': 0.9, 'autumn': 0.9, 'winter': 1.0},
            'repot_offset': 0,
            'graft_offset': 0,
        }
    },
    'arid': {
        'name': '干旱半干旱',
        'desc': '降水少蒸发大，空气干燥，需注意增湿和遮阴',
        'adjust': {
            'water':   {'spring': 0.75, 'summer': 0.7, 'autumn': 0.75, 'winter': 0.85},
            'fertilize':{'spring': 0.9, 'summer': 0.85, 'autumn': 0.9, 'winter': 1.0},
            'repot_offset': 0,
            'graft_offset': 0,
        }
    },
}

# 城市到气候带的映射（涵盖全国主要城市）
CITY_CLIMATE = {
    # 热带
    '海口': 'tropical', '三亚': 'tropical', '三沙': 'tropical', '儋州': 'tropical', '琼海': 'tropical', '万宁': 'tropical',
    # 亚热带
    '上海': 'subtropical', '南京': 'subtropical', '杭州': 'subtropical', '苏州': 'subtropical',
    '无锡': 'subtropical', '宁波': 'subtropical', '温州': 'subtropical', '绍兴': 'subtropical',
    '合肥': 'subtropical', '芜湖': 'subtropical', '蚌埠': 'subtropical',
    '武汉': 'subtropical', '宜昌': 'subtropical', '襄阳': 'subtropical', '荆州': 'subtropical',
    '长沙': 'subtropical', '株洲': 'subtropical', '湘潭': 'subtropical', '衡阳': 'subtropical',
    '南昌': 'subtropical', '九江': 'subtropical', '赣州': 'subtropical', '吉安': 'subtropical',
    '成都': 'subtropical', '绵阳': 'subtropical', '德阳': 'subtropical', '宜宾': 'subtropical',
    '乐山': 'subtropical', '泸州': 'subtropical', '南充': 'subtropical', '达州': 'subtropical',
    '重庆': 'subtropical', '万州': 'subtropical', '涪陵': 'subtropical',
    '广州': 'subtropical', '深圳': 'subtropical', '东莞': 'subtropical', '佛山': 'subtropical',
    '珠海': 'subtropical', '中山': 'subtropical', '惠州': 'subtropical', '江门': 'subtropical',
    '汕头': 'subtropical', '湛江': 'subtropical', '茂名': 'subtropical', '肇庆': 'subtropical',
    '福州': 'subtropical', '厦门': 'subtropical', '泉州': 'subtropical', '漳州': 'subtropical',
    '莆田': 'subtropical', '南平': 'subtropical', '龙岩': 'subtropical',
    '南宁': 'subtropical', '柳州': 'subtropical', '桂林': 'subtropical', '梧州': 'subtropical',
    '北海': 'subtropical', '玉林': 'subtropical', '百色': 'subtropical',
    '贵阳': 'subtropical', '遵义': 'subtropical', '六盘水': 'subtropical',
    '昆明': 'subtropical', '玉溪': 'subtropical', '曲靖': 'subtropical',
    '台北': 'subtropical', '高雄': 'subtropical', '台中': 'subtropical',
    # 暖温带
    '北京': 'warm_temp', '天津': 'warm_temp', '石家庄': 'warm_temp', '唐山': 'warm_temp',
    '保定': 'warm_temp', '秦皇岛': 'warm_temp', '邯郸': 'warm_temp', '廊坊': 'warm_temp',
    '济南': 'warm_temp', '青岛': 'warm_temp', '烟台': 'warm_temp', '潍坊': 'warm_temp',
    '临沂': 'warm_temp', '济宁': 'warm_temp', '淄博': 'warm_temp', '威海': 'warm_temp',
    '郑州': 'warm_temp', '洛阳': 'warm_temp', '开封': 'warm_temp', '南阳': 'warm_temp',
    '新乡': 'warm_temp', '安阳': 'warm_temp', '许昌': 'warm_temp',
    '西安': 'warm_temp', '咸阳': 'warm_temp', '宝鸡': 'warm_temp', '渭南': 'warm_temp',
    '铜川': 'warm_temp', '汉中': 'warm_temp',
    '太原': 'warm_temp', '大同': 'warm_temp', '临汾': 'warm_temp', '运城': 'warm_temp',
    '长治': 'warm_temp', '晋城': 'warm_temp',
    '大连': 'warm_temp', '连云港': 'warm_temp', '徐州': 'warm_temp',
    '兰州': 'warm_temp', '白银': 'warm_temp', '天水': 'warm_temp', '平凉': 'warm_temp',
    '银川': 'warm_temp', '石嘴山': 'warm_temp', '吴忠': 'warm_temp',
    '西宁': 'warm_temp',
    # 中温带
    '沈阳': 'mid_temp', '大连北': 'mid_temp', '鞍山': 'mid_temp', '抚顺': 'mid_temp',
    '锦州': 'mid_temp', '丹东': 'mid_temp', '营口': 'mid_temp', '阜新': 'mid_temp',
    '长春': 'mid_temp', '吉林': 'mid_temp', '四平': 'mid_temp', '辽源': 'mid_temp',
    '通化': 'mid_temp', '松原': 'mid_temp', '白城': 'mid_temp',
    '哈尔滨': 'mid_temp', '齐齐哈尔': 'mid_temp', '牡丹江': 'mid_temp', '佳木斯': 'mid_temp',
    '大庆': 'mid_temp', '绥化': 'mid_temp', '鸡西': 'mid_temp', '鹤岗': 'mid_temp',
    '呼和浩特': 'mid_temp', '包头': 'mid_temp', '赤峰': 'mid_temp', '通辽': 'mid_temp',
    '鄂尔多斯': 'mid_temp', '乌兰察布': 'mid_temp',
    '乌鲁木齐': 'mid_temp', '克拉玛依': 'mid_temp', '昌吉': 'mid_temp',
    '吐鲁番': 'mid_temp', '哈密': 'mid_temp',
    '张家口': 'mid_temp', '承德': 'mid_temp',
    # 寒温带
    '漠河': 'cold_temp', '根河': 'cold_temp', '呼伦贝尔': 'cold_temp',
    '黑河': 'cold_temp', '伊春': 'cold_temp', '大兴安岭': 'cold_temp',
    '加格达奇': 'cold_temp',
    # 高原气候
    '拉萨': 'plateau', '日喀则': 'plateau', '林芝': 'plateau', '山南': 'plateau',
    '丽江': 'plateau', '大理': 'plateau', '迪庆': 'plateau', '香格里拉': 'plateau',
    '攀枝花': 'plateau', '西昌': 'plateau',
    '格尔木': 'plateau',
    # 干旱半干旱
    '喀什': 'arid', '阿克苏': 'arid', '和田': 'arid', '库尔勒': 'arid',
    '敦煌': 'arid', '嘉峪关': 'arid', '酒泉': 'arid', '张掖': 'arid',
    '武威': 'arid', '金昌': 'arid',
    '巴彦淖尔': 'arid', '阿拉善': 'arid',
}

def get_climate_zone(city):
    """根据城市名获取气候带信息"""
    zone_id = CITY_CLIMATE.get(city, 'warm_temp')  # 默认暖温带
    return zone_id, CLIMATE_ZONES[zone_id]

def adjust_interval(base_str, factor):
    """根据气候系数调整周期字符串，如 '3-4天' * 0.8 -> '3天'"""
    import re
    if not base_str or '停' in base_str or '不需' in base_str or '无需' in base_str:
        return base_str
    nums = re.findall(r'\d+', str(base_str))
    if not nums:
        return base_str
    if len(nums) >= 2:
        new_a = max(1, round(int(nums[0]) * factor))
        new_b = max(new_a + 1, round(int(nums[1]) * factor))
        return f'{new_a}-{new_b}天'
    else:
        new_val = max(1, round(int(nums[0]) * factor))
        return f'{new_val}天'

def get_adjusted_season_care(flower_row, climate_zone_id, season):
    """获取经过气候调整后的单季养护数据"""
    zone = CLIMATE_ZONES.get(climate_zone_id, CLIMATE_ZONES['warm_temp'])
    adj = zone['adjust']

    water_key = f'{season}_water'
    fert_key = f'{season}_fertilize'
    tips_key = f'{season}_tips'

    base_water = flower_row[water_key] if water_key in flower_row.keys() else ''
    base_fert = flower_row[fert_key] if fert_key in flower_row.keys() else ''

    water_factor = adj['water'].get(season, 1.0)
    fert_factor = adj['fertilize'].get(season, 1.0)

    adjusted_water = adjust_interval(base_water, water_factor)
    adjusted_fert = adjust_interval(base_fert, fert_factor)

    return {
        'water': adjusted_water,
        'fertilize': adjusted_fert,
        'tips': flower_row[tips_key] if tips_key in flower_row.keys() else '',
        'water_original': base_water,
        'fertilize_original': base_fert,
    }


# ---------- Climate API ----------
@app.route('/api/climate', methods=['GET'])
def get_climate():
    """根据城市返回气候信息和调整系数"""
    city = request.args.get('city', '').strip()
    if not city:
        return jsonify({'error': '请提供城市参数'}), 400
    zone_id, zone_info = get_climate_zone(city)
    return jsonify({
        'city': city,
        'zone_id': zone_id,
        'zone_name': zone_info['name'],
        'zone_desc': zone_info['desc'],
        'adjust': zone_info['adjust']
    })


# ==================== USER AVATAR ====================
AVATAR_DIR = os.path.join(WORK_DIR, 'avatars')

@app.route('/avatars/<path:filename>')
def serve_avatar(filename):
    """提供用户头像文件"""
    return send_from_directory(AVATAR_DIR, filename)

@app.route('/api/user/<int:user_id>/avatar', methods=['POST'])
def upload_avatar(user_id):
    """上传用户头像"""
    db = get_db()
    user = db.execute('SELECT id, avatar FROM users WHERE id=?', (user_id,)).fetchone()
    if not user:
        return jsonify({'error': '用户不存在'}), 404

    if 'photo' not in request.files:
        return jsonify({'error': '请选择照片文件'}), 400

    file = request.files['photo']
    if file.filename == '':
        return jsonify({'error': '请选择照片文件'}), 400

    # Validate file type
    allowed_ext = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in allowed_ext:
        return jsonify({'error': '仅支持 JPG/PNG/WebP/GIF 格式'}), 400

    # Ensure directory exists
    os.makedirs(AVATAR_DIR, exist_ok=True)

    # Delete old avatar file if exists
    old_avatar = user['avatar'] if 'avatar' in user.keys() else ''
    if old_avatar:
        old_path = os.path.join(WORK_DIR, old_avatar.lstrip('/'))
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    # Generate unique filename
    unique_name = f"{user_id}_{uuid.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(AVATAR_DIR, unique_name)
    file.save(save_path)

    # Update database
    avatar_url = f'/avatars/{unique_name}'
    db.execute('UPDATE users SET avatar=? WHERE id=?', (avatar_url, user_id))
    db.commit()

    return jsonify({'success': True, 'avatar': avatar_url})


# ==================== PLANT PHOTOS & IDENTIFICATION ====================
PLANT_PHOTOS_DIR = os.path.join(WORK_DIR, 'plant_photos')

@app.route('/plant_photos/<path:filename>')
def serve_plant_photo(filename):
    """提供植株照片文件"""
    return send_from_directory(PLANT_PHOTOS_DIR, filename)

@app.route('/api/user/<int:user_id>/plants/<int:plant_id>/photo', methods=['POST'])
def upload_plant_photo(user_id, plant_id):
    """上传植株照片"""
    db = get_db()
    plant = db.execute('SELECT id, photo FROM my_plants WHERE id=? AND user_id=?', (plant_id, user_id)).fetchone()
    if not plant:
        return jsonify({'error': '植株不存在'}), 404

    if 'photo' not in request.files:
        return jsonify({'error': '请选择照片文件'}), 400

    file = request.files['photo']
    if file.filename == '':
        return jsonify({'error': '请选择照片文件'}), 400

    # Validate file type
    allowed_ext = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in allowed_ext:
        return jsonify({'error': '仅支持 JPG/PNG/WebP/GIF 格式'}), 400

    # Ensure directory exists
    os.makedirs(PLANT_PHOTOS_DIR, exist_ok=True)

    # Delete old photo file if exists
    old_photo = plant['photo']
    if old_photo:
        old_path = os.path.join(WORK_DIR, old_photo.lstrip('/'))
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    # Generate unique filename
    unique_name = f"{user_id}_{plant_id}_{uuid.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(PLANT_PHOTOS_DIR, unique_name)
    file.save(save_path)

    # Update database
    photo_url = f'/plant_photos/{unique_name}'
    db.execute('UPDATE my_plants SET photo=? WHERE id=? AND user_id=?', (photo_url, plant_id, user_id))
    db.commit()

    return jsonify({'success': True, 'photo': photo_url})


@app.route('/api/user/<int:user_id>/plants/<int:plant_id>/identify', methods=['POST'])
def identify_plant(user_id, plant_id):
    """基于知识库的植物识别/确认"""
    db = get_db()
    plant = db.execute('SELECT id, flower_id, photo, identify_result FROM my_plants WHERE id=? AND user_id=?',
                       (plant_id, user_id)).fetchone()
    if not plant:
        return jsonify({'error': '植株不存在'}), 404

    flower_id = plant['flower_id']

    # Get full flower knowledge for identification result
    fk = db.execute('''SELECT flower_id, name, emoji, desc, soil,
                              spring_water, summer_water, autumn_water, winter_water,
                              spring_fertilize, summer_fertilize, autumn_fertilize, winter_fertilize,
                              spring_tips, summer_tips, autumn_tips, winter_tips,
                              grafting, repot
                       FROM flower_knowledge WHERE flower_id=?''', (flower_id,)).fetchone()
    if not fk:
        return jsonify({'error': '花卉知识未找到'}), 404

    # Build identification result based on knowledge base
    # Since the plant is already categorized under a flower type,
    # we provide a rich "confirmation" with care tips and health advice
    fk_dict = dict(fk)

    # Get climate-adjusted current season care
    user = db.execute('SELECT city FROM users WHERE id=?', (user_id,)).fetchone()
    city = user['city'] if user else ''
    zone_id, _ = get_climate_zone(city) if city else ('warm_temp', CLIMATE_ZONES['warm_temp'])

    now = datetime.now()
    month = now.month
    if month in (3,4,5): season = 'spring'
    elif month in (6,7,8): season = 'summer'
    elif month in (9,10,11): season = 'autumn'
    else: season = 'winter'

    season_care = get_adjusted_season_care(fk_dict, zone_id, season)

    season_names = {'spring': '春季', 'summer': '夏季', 'autumn': '秋季', 'winter': '冬季'}

    # Build the identification result
    result = {
        'confirmed': True,
        'flower_id': flower_id,
        'name': fk_dict['name'],
        'emoji': fk_dict['emoji'],
        'confidence': 'high',  # High confidence since user already categorized it
        'description': fk_dict['desc'],
        'current_season': season_names.get(season, season),
        'care_advice': {
            'water': season_care['water'],
            'fertilize': season_care['fertilize'],
            'tips': season_care['tips'],
        },
        'soil': fk_dict['soil'],
        'repot': fk_dict['repot'],
        'grafting': fk_dict['grafting'],
        'zone_info': {
            'city': city or '未设置',
            'zone_name': CLIMATE_ZONES.get(zone_id, {}).get('name', '暖温带'),
        },
        'health_suggestions': _generate_health_suggestions(fk_dict, season, zone_id),
    }

    # Save identification result to database
    result_json = json.dumps(result, ensure_ascii=False)
    db.execute('UPDATE my_plants SET identify_result=? WHERE id=?', (result_json, plant_id))
    db.commit()

    return jsonify({'success': True, 'result': result})


def _generate_health_suggestions(fk_dict, season, zone_id):
    """根据花卉知识和当前季节生成健康建议"""
    suggestions = []
    water_key = f'{season}_water'
    fert_key = f'{season}_fertilize'
    tips_key = f'{season}_tips'

    water = fk_dict.get(water_key, '')
    fert = fk_dict.get(fert_key, '')
    tips = fk_dict.get(tips_key, '')

    # watering suggestion
    if water:
        if '停' in water or '不需' in water or '减少' in water:
            suggestions.append('当前季节需控水，注意不要过度浇水，避免根部腐烂')
        elif '勤' in water or '多' in water or '每天' in water:
            suggestions.append('当前季节需水量大，注意保持土壤湿润，避免缺水黄叶')
        else:
            suggestions.append(f'当前季节建议浇水频率: {water}，遵循"见干见湿"原则')

    # fertilizing suggestion
    if fert:
        if '停' in fert or '不需' in fert or '无需' in fert:
            suggestions.append('当前季节不宜施肥，休眠期施肥易烧根')
        else:
            suggestions.append(f'当前季节可适当施肥: {fert}')

    # seasonal tips
    if tips:
        suggestions.append(tips)

    # general health advice
    zone_info = CLIMATE_ZONES.get(zone_id, {})
    zone_name = zone_info.get('name', '')
    if zone_name in ('热带', '亚热带') and season == 'summer':
        suggestions.append('高温季节注意通风遮阴，避免闷根')
    elif zone_name in ('中温带', '寒温带') and season == 'winter':
        suggestions.append('严寒季节注意保暖防冻，建议移至室内养护')
    elif zone_name == '高原气候':
        suggestions.append('高原地区紫外线强，注意适当遮阴，增加浇水频率')

    return suggestions


# ==================== MAIN ====================
if __name__ == '__main__':
    init_db()
    print('='*40)
    print('  花卉养殖助手 - 服务器已启动')
    print('  http://localhost:8765')
    print('  浏览器将自动打开...')
    print('  关闭此窗口将停止服务器')
    print('='*40)

    # 自动打开浏览器
    import webbrowser
    import threading
    def open_browser():
        import time
        time.sleep(2)
        url = 'http://localhost:8765'
        try:
            webbrowser.open(url)
        except Exception:
            try:
                os.startfile(url)
            except Exception:
                try:
                    import subprocess
                    subprocess.Popen(['cmd', '/c', 'start', '', url])
                except Exception:
                    print('提示: 请手动打开浏览器访问 http://localhost:8765')
    threading.Thread(target=open_browser, daemon=True).start()

    app.run(host='0.0.0.0', port=8765, debug=False)
