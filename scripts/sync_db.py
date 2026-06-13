import sqlite3
import json
import os
from pathlib import Path

# 动态解析项目根目录，避免依赖调用命令时的工作目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def sync_labels_to_db():
    db_path = str(PROJECT_ROOT / 'data' / 'app.db')
    label_path = str(PROJECT_ROOT / 'data' / 'models' / 'label_map.json')

    print("🔄 开始执行数据注入...")

    if not os.path.exists(label_path) or not os.path.exists(db_path):
        print("❌ 找不到字典或数据库文件，请检查路径。")
        return

    with open(label_path, 'r', encoding='utf-8') as f:
        label_map = json.load(f)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    success_count = 0
    update_count = 0
    insert_count = 0

    for idx, info in label_map.items():
        label = info['en']
        zh_name = info['zh']
        default_price = 9.90  # 测试单价：9.9元/kg
        
        try:
            # 1. 先查查库里有没有这个 label
            cursor.execute("SELECT id FROM products WHERE label = ?", (label,))
            row = cursor.fetchone()
            
            if row:
                # 2. 如果队友之前塞过这个商品，我们就只更新名字和价格
                cursor.execute('''
                    UPDATE products 
                    SET name_cn = ?, price_per_kg = ? 
                    WHERE label = ?
                ''', (zh_name, default_price, label))
                update_count += 1
            else:
                # 3. 如果是新商品，直接插入
                cursor.execute('''
                    INSERT INTO products (label, name_cn, price_per_kg) 
                    VALUES (?, ?, ?)
                ''', (label, zh_name, default_price))
                insert_count += 1
                
            success_count += 1
            
        except Exception as e:
            print(f"⚠️ 处理 {label} 时出错: {e}")

    conn.commit()
    conn.close()
    
    print("-" * 40)
    print(f"✅ 数据库同步大功告成！共处理 {success_count} 种果蔬。")
    print(f"📊 详情: 新增 {insert_count} 条，更新 {update_count} 条。")
    print("🚀 最后一公里已打通，请重新启动 main.py！")

if __name__ == '__main__':
    sync_labels_to_db()