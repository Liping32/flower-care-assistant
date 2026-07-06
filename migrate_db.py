#!/usr/bin/env python3
"""Safe database migration for flower-care-assistant.
- Creates user_flower_config table if not exists
- Inserts 3 new flowers (money_tree, snake_plant, peperomia) if not exists
- Initializes user_flower_config for all existing users
- Does NOT modify or delete any existing user data
"""
import sqlite3, json, os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flower_care.db')
db = sqlite3.connect(DB)

# 1. Create user_flower_config table if not exists
db.execute('''CREATE TABLE IF NOT EXISTS user_flower_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    flower_id TEXT NOT NULL,
    visible INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    UNIQUE(user_id, flower_id)
)''')
print('1. user_flower_config table ensured')

# 2. Insert 3 new flowers if not exist (INSERT OR IGNORE is safe)
flowers = [
    ('money_tree', '\u53d1\u8d22\u6811', '\U0001f4b0',
     '/images/money_tree-cover.jpg',
     json.dumps(['/images/money_tree-closeup.jpg', '/images/money_tree-full.jpg', '/images/money_tree-side.jpg']),
     json.dumps(['\u7279\u5199', '\u5168\u682a', '\u4fa7\u666f']),
     '\u62db\u8d22\u5409\u7965\uff0c\u56db\u5b63\u5e38\u9752\uff0c\u5ba4\u5185\u65fa\u8fd0',
     '\u758f\u677e\u900f\u6c14\u7684\u5fae\u9178\u6027\u571f\u58e4\uff0c\u8150\u53f6\u571f+\u56ed\u571f+\u6cb3\u6c99(4:3:3)\uff0c\u5fcc\u79ef\u6c34',
     '7-10\u5929','\u6bcf\u6708\u4e00\u6b21\u7a00\u8584\u6db2\u80a5','\u6625\u5b63\u6362\u76c6\u4fee\u526a\uff0c\u9010\u6b65\u589e\u52a0\u6d47\u6c34\u91cf',
     '10-15\u5929','\u4e0d\u9700','\u590f\u5b63\u751f\u957f\u7f13\u6162\u5fcc\u6d53\u80a5\uff0c\u4fdd\u6301\u901a\u98ce\uff0c\u907f\u514d\u70c8\u65e5\u76f4\u5c04',
     '7-10\u5929','\u6bcf\u6708\u4e00\u6b21\u590d\u5408\u80a5','\u79cb\u5b63\u51cf\u5c11\u6d47\u6c34\uff0c\u589e\u65bd\u78f7\u94be\u80a5\u589e\u5f3a\u6297\u6027',
     '15-20\u5929','\u505c\u6b62\u65bd\u80a5','\u4fdd\u669610\u00b0C\u4ee5\u4e0a\uff0c\u51cf\u5c11\u6d47\u6c34\uff0c\u53f6\u7247\u55b7\u6c34\u4fdd\u6da6',
     '\u6266\u63d2\u7e41\u6b96\uff0c\u6625\u590f\u53d6\u9876\u82bd\u63d2\u5165\u6c99\u5e8a\uff0c\u4fdd\u6301\u6e7f\u6da630\u5929\u751f\u6839\uff1b\u4e5f\u53ef\u64ad\u79cd',
     '2\u5e74\u6362\u76c6\u4e00\u6b21\uff0c\u6625\u5b63\u8fdb\u884c\uff0c\u4fee\u526a\u8001\u6839\uff0c\u76c6\u5e95\u52a0\u539a\u6392\u6c34\u5c42'),
    ('snake_plant', '\u864e\u76ae\u5170', '\U0001f5e1\ufe0f',
     '/images/snake_plant-cover.jpg',
     json.dumps(['/images/snake_plant-closeup.jpg', '/images/snake_plant-full.jpg', '/images/snake_plant-side.jpg']),
     json.dumps(['\u7279\u5199', '\u5168\u682a', '\u4fa7\u666f']),
     '\u631a\u62d4\u521a\u52b2\uff0c\u51c0\u5316\u7a7a\u6c14\uff0c\u61d2\u4eba\u6700\u7231',
     '\u758f\u677e\u900f\u6c14\u7684\u6c99\u8d28\u58e4\u571f\uff0c\u56ed\u571f+\u6cb3\u6c99+\u8150\u53f6\u571f(3:4:3)\uff0c\u5fcc\u9ecf\u91cd\u79ef\u6c34',
     '7-10\u5929','\u6bcf\u6708\u4e00\u6b21\u7a00\u8584\u6db2\u80a5','\u6625\u6696\u589e\u52a0\u5149\u7167\uff0c\u53ef\u5206\u682a\u7e41\u6b96',
     '10-15\u5929','\u4e0d\u9700','\u8010\u65f1\u8010\u9634\uff0c\u590f\u5b63\u5e87\u836b\uff0c\u76c6\u571f\u5e72\u900f\u518d\u6d47\uff0c\u5fcc\u79ef\u6c34',
     '7-10\u5929','\u6bcf\u6708\u4e00\u6b21\u78f7\u94be\u80a5','\u79cb\u5b63\u51cf\u5c11\u6d47\u6c34\uff0c\u589e\u52a0\u5149\u7167',
     '15-20\u5929','\u505c\u6b62\u65bd\u80a5','\u8010\u9634\u8010\u65f1\uff0c5\u00b0C\u4ee5\u4e0a\u53ef\u8d8a\u51ac\uff0c\u63a7\u6c34\u4e3a\u4e3b',
     '\u5206\u682a\u7e41\u6b96\u6700\u7b80\u5355\uff0c\u6625\u5b63\u8131\u76c6\u5206\u5207\uff1b\u53f6\u63d2\u4e5f\u53ef\uff0c\u53d68cm\u53f6\u6bb5\u63d2\u5165\u6c99\u4e2d',
     '2-3\u5e74\u6362\u76c6\u4e00\u6b21\uff0c\u6625\u5b63\u8fdb\u884c\uff0c\u6839\u7cfb\u6d45\u7528\u6d45\u76c6\uff0c\u6392\u6c34\u5c42\u8981\u539a'),
    ('peperomia', '\u78a7\u7389', '\U0001f49a',
     '/images/peperomia-cover.jpg',
     json.dumps(['/images/peperomia-closeup.jpg', '/images/peperomia-full.jpg', '/images/peperomia-side.jpg']),
     json.dumps(['\u7279\u5199', '\u5168\u682a', '\u4fa7\u666f']),
     '\u5706\u6da6\u53ef\u7231\uff0c\u78a7\u7eff\u5982\u7389\uff0c\u684c\u9762\u5c0f\u6e05\u65b0',
     '\u758f\u677e\u900f\u6c14\u7684\u8150\u6b96\u571f\uff0c\u8150\u53f6\u571f+\u6cb3\u6c99+\u73cd\u73e0\u5ca9(4:3:3)\uff0c\u5fcc\u79ef\u6c34',
     '5-7\u5929','\u6bcf\u6708\u4e00\u6b21\u7a00\u8584\u6db2\u80a5','\u6625\u5b63\u6362\u76c6\u4fee\u526a\uff0c\u5206\u682a\u6266\u63d2\u597d\u65f6\u673a',
     '3-5\u5929','\u4e0d\u9700','\u590f\u5b63\u5fcc\u70c8\u65e5\u76f4\u5c04\uff0c\u6563\u5c04\u5149\u4e3a\u4e3b\uff0c\u89c1\u5e72\u89c1\u6e7f',
     '5-7\u5929','\u6bcf\u6708\u4e00\u6b21\u590d\u5408\u80a5','\u79cb\u5b63\u51cf\u5c11\u6d47\u6c34\uff0c\u9002\u5f53\u589e\u52a0\u5149\u7167',
     '7-10\u5929','\u505c\u6b62\u65bd\u80a5','\u4fdd\u669610\u00b0C\u4ee5\u4e0a\uff0c\u63a7\u6c34\u4fdd\u5fae\u6da6\uff0c\u53f6\u9762\u53ef\u55b7\u6c34',
     '\u53f6\u63d2\u4e3a\u4e3b\uff0c\u53d6\u5065\u5eb7\u53f6\u7247\u5e26\u53f6\u67c4\u63d2\u5165\u6c99\u4e2d\uff0c20\u5929\u751f\u6839\uff1b\u4e5f\u53ef\u5206\u682a\u6216\u830e\u63d2',
     '\u6bcf\u5e74\u6625\u5b63\u6362\u76c6\uff0c\u6d45\u76c6\u4e3a\u4f73\uff0c\u4fdd\u7559\u62a4\u5fc3\u571f\uff0c\u6392\u6c34\u8981\u597d'),
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
print('2. Inserted 3 new flowers (or already existed)')

# 3. Init default config for all existing users
users = [r[0] for r in db.execute('SELECT id FROM users').fetchall()]
flowers_all = [r[0] for r in db.execute('SELECT flower_id FROM flower_knowledge ORDER BY id').fetchall()]
print(f'3. Found {len(users)} users, {len(flowers_all)} flowers')
for uid in users:
    existing = [r[0] for r in db.execute('SELECT flower_id FROM user_flower_config WHERE user_id=?', (uid,)).fetchall()]
    if not existing:
        for idx, fid in enumerate(flowers_all):
            db.execute('INSERT OR IGNORE INTO user_flower_config (user_id, flower_id, visible, sort_order) VALUES (?,?,1,?)', (uid, fid, idx))
        print(f'   Init config for user {uid}: {len(flowers_all)} flowers')
    else:
        # Add new flowers to existing config if not present
        for fid in flowers_all:
            if fid not in existing:
                db.execute('INSERT OR IGNORE INTO user_flower_config (user_id, flower_id, visible, sort_order) VALUES (?,?,1,99)', (uid, fid))
                print(f'   Added {fid} to user {uid} config')

db.commit()

# Verify
cur = db.execute('SELECT flower_id, name FROM flower_knowledge WHERE flower_id IN (?,?,?)', ('money_tree','snake_plant','peperomia'))
print('4. New flowers in DB:')
for row in cur:
    print(f'   {row[0]}: {row[1]}')

cfg_count = db.execute('SELECT COUNT(*) FROM user_flower_config').fetchone()[0]
print(f'5. Total user_flower_config rows: {cfg_count}')

db.close()
print('DONE - Migration complete, no existing data modified')
