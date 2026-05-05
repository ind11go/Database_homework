from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from database import get_connection, init_database
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'campus-trade-secret-key'


# 应用启动时自动初始化数据库（确保部署环境也有数据）
with app.app_context():
    if not os.path.exists('campus_trade.db'):
        init_database()


@app.before_request
def enable_foreign_keys():
    conn = get_connection()
    conn.execute('PRAGMA foreign_keys = ON')
    conn.close()


# ==================== 页面路由 ====================

@app.route('/')
def index():
    conn = get_connection()
    cursor = conn.cursor()

    stats = {
        'user_count': cursor.execute('SELECT COUNT(*) FROM User').fetchone()[0],
        'item_count': cursor.execute('SELECT COUNT(*) FROM Item').fetchone()[0],
        'order_count': cursor.execute('SELECT COUNT(*) FROM Orders').fetchone()[0],
        'sold_count': cursor.execute('SELECT COUNT(*) FROM Item WHERE status = 1').fetchone()[0],
        'unsold_count': cursor.execute('SELECT COUNT(*) FROM Item WHERE status = 0').fetchone()[0],
    }

    recent_items = cursor.execute(
        'SELECT item_id, item_name, category, price, status FROM Item ORDER BY item_id DESC LIMIT 5'
    ).fetchall()

    recent_orders = cursor.execute(
        '''SELECT o.order_id, i.item_name, u.user_name as buyer_name, o.order_date
           FROM Orders o
           JOIN Item i ON o.item_id = i.item_id
           JOIN User u ON o.buyer_id = u.user_id
           ORDER BY o.order_date DESC LIMIT 5'''
    ).fetchall()

    conn.close()
    return render_template('index.html', stats=stats, recent_items=recent_items, recent_orders=recent_orders)


@app.route('/users')
def users():
    conn = get_connection()
    cursor = conn.cursor()
    all_users = cursor.execute('SELECT * FROM User').fetchall()

    # 聚合查询：每个用户发布的商品数量
    user_item_counts = cursor.execute(
        '''SELECT u.user_id, u.user_name, COUNT(i.item_id) as item_count
           FROM User u
           LEFT JOIN Item i ON u.user_id = i.seller_id
           GROUP BY u.user_id'''
    ).fetchall()

    # 查询发布商品数量最多的用户
    top_seller = cursor.execute(
        '''SELECT u.user_id, u.user_name, COUNT(i.item_id) as item_count
           FROM User u
           JOIN Item i ON u.user_id = i.seller_id
           GROUP BY u.user_id
           ORDER BY item_count DESC
           LIMIT 1'''
    ).fetchone()

    conn.close()
    return render_template('users.html', users=all_users, user_item_counts=user_item_counts, top_seller=top_seller)


@app.route('/items', methods=['GET', 'POST'])
def items():
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            item_id = request.form.get('item_id')
            item_name = request.form.get('item_name')
            category = request.form.get('category')
            price = float(request.form.get('price'))
            seller_id = request.form.get('seller_id')

            try:
                cursor.execute(
                    'INSERT INTO Item (item_id, item_name, category, price, status, seller_id) VALUES (?, ?, ?, ?, 0, ?)',
                    (item_id, item_name, category, price, seller_id)
                )
                conn.commit()
                flash(f'商品 {item_name} 添加成功！', 'success')
            except sqlite3.IntegrityError as e:
                flash(f'添加失败：{str(e)}', 'error')

        elif action == 'update_price':
            item_id = request.form.get('item_id')
            new_price = float(request.form.get('new_price'))
            cursor.execute('UPDATE Item SET price = ? WHERE item_id = ?', (new_price, item_id))
            conn.commit()
            flash(f'商品 {item_id} 价格已更新为 {new_price}', 'success')

        elif action == 'delete':
            item_id = request.form.get('item_id')
            # 只能删除未售出的商品
            item = cursor.execute('SELECT * FROM Item WHERE item_id = ?', (item_id,)).fetchone()
            if item and item['status'] == 0:
                cursor.execute('DELETE FROM Item WHERE item_id = ?', (item_id,))
                conn.commit()
                flash(f'商品 {item_id} 已删除', 'success')
            else:
                flash('只能删除未售出的商品！', 'error')

        conn.close()
        return redirect(url_for('items'))

    all_items = cursor.execute(
        '''SELECT i.*, u.user_name as seller_name
           FROM Item i
           JOIN User u ON i.seller_id = u.user_id'''
    ).fetchall()

    all_users = cursor.execute('SELECT user_id, user_name FROM User').fetchall()

    # 基本查询
    unsold_items = cursor.execute('SELECT * FROM Item WHERE status = 0').fetchall()
    expensive_items = cursor.execute('SELECT * FROM Item WHERE price > 30').fetchall()
    daily_goods = cursor.execute("SELECT * FROM Item WHERE category = 'DailyGoods'").fetchall()
    u001_items = cursor.execute("SELECT * FROM Item WHERE seller_id = 'u001'").fetchall()

    # 连接查询：所有已售商品及其买家姓名
    sold_with_buyer = cursor.execute(
        '''SELECT i.item_name, u.user_name as buyer_name
           FROM Item i
           JOIN Orders o ON i.item_id = o.item_id
           JOIN User u ON o.buyer_id = u.user_id'''
    ).fetchall()

    # 连接查询：每个订单详情
    order_details = cursor.execute(
        '''SELECT i.item_name, u.user_name as buyer_name, o.order_date
           FROM Orders o
           JOIN Item i ON o.item_id = i.item_id
           JOIN User u ON o.buyer_id = u.user_id'''
    ).fetchall()

    # 连接查询：u001的商品是否被购买
    u001_sold_check = cursor.execute(
        '''SELECT i.item_name,
                  CASE WHEN o.order_id IS NOT NULL THEN '已购买' ELSE '未售出' END as status
           FROM Item i
           LEFT JOIN Orders o ON i.item_id = o.item_id
           WHERE i.seller_id = 'u001'
        '''
    ).fetchall()

    # 聚合查询
    total_items = cursor.execute('SELECT COUNT(*) as count FROM Item').fetchone()
    category_counts = cursor.execute(
        'SELECT category, COUNT(*) as count FROM Item GROUP BY category'
    ).fetchall()
    avg_price = cursor.execute('SELECT AVG(price) as avg_price FROM Item').fetchone()

    conn.close()
    return render_template('items.html', items=all_items, users=all_users,
                          unsold_items=unsold_items, expensive_items=expensive_items,
                          daily_goods=daily_goods, u001_items=u001_items,
                          sold_with_buyer=sold_with_buyer, order_details=order_details,
                          u001_sold_check=u001_sold_check, total_items=total_items,
                          category_counts=category_counts, avg_price=avg_price)


@app.route('/orders', methods=['GET', 'POST'])
def orders():
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'buy':
            order_id = request.form.get('order_id')
            item_id = request.form.get('item_id')
            buyer_id = request.form.get('buyer_id')
            order_date = request.form.get('order_date')

            try:
                # 使用事务确保原子性
                conn.execute('BEGIN TRANSACTION')

                # 检查商品是否已售出
                item = cursor.execute('SELECT status FROM Item WHERE item_id = ?', (item_id,)).fetchone()
                if not item:
                    raise Exception('商品不存在')
                if item['status'] == 1:
                    raise Exception('商品已售出，不能再次购买')

                # 更新商品状态为已售出
                cursor.execute('UPDATE Item SET status = 1 WHERE item_id = ?', (item_id,))

                # 插入订单记录
                cursor.execute(
                    'INSERT INTO Orders (order_id, item_id, buyer_id, order_date) VALUES (?, ?, ?, ?)',
                    (order_id, item_id, buyer_id, order_date)
                )

                conn.commit()
                flash('购买成功！', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'购买失败：{str(e)}', 'error')

        conn.close()
        return redirect(url_for('orders'))

    all_orders = cursor.execute(
        '''SELECT o.*, i.item_name, u.user_name as buyer_name
           FROM Orders o
           JOIN Item i ON o.item_id = i.item_id
           JOIN User u ON o.buyer_id = u.user_id'''
    ).fetchall()

    # 可购买的商品（未售出）
    available_items = cursor.execute(
        "SELECT item_id, item_name FROM Item WHERE status = 0"
    ).fetchall()

    all_users = cursor.execute('SELECT user_id, user_name FROM User').fetchall()

    conn.close()
    return render_template('orders.html', orders=all_orders,
                          available_items=available_items, users=all_users)


@app.route('/queries')
def queries():
    conn = get_connection()
    cursor = conn.cursor()

    # 视图查询
    sold_view = cursor.execute('SELECT * FROM SoldItemsView').fetchall()
    unsold_view = cursor.execute('SELECT * FROM UnsoldItemsView').fetchall()

    conn.close()
    return render_template('queries.html', sold_view=sold_view, unsold_view=unsold_view)


# ==================== API 路由（用于AJAX操作） ====================

@app.route('/api/items', methods=['POST'])
def api_add_item():
    data = request.get_json()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO Item (item_id, item_name, category, price, status, seller_id) VALUES (?, ?, ?, ?, 0, ?)',
            (data['item_id'], data['item_name'], data['category'], data['price'], data['seller_id'])
        )
        conn.commit()
        return jsonify({'success': True, 'message': '添加成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()


@app.route('/api/items/<item_id>/price', methods=['PUT'])
def api_update_price(item_id):
    data = request.get_json()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE Item SET price = ? WHERE item_id = ?', (data['price'], item_id))
        conn.commit()
        return jsonify({'success': True, 'message': '价格更新成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()


@app.route('/api/items/<item_id>', methods=['DELETE'])
def api_delete_item(item_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        item = cursor.execute('SELECT status FROM Item WHERE item_id = ?', (item_id,)).fetchone()
        if not item:
            return jsonify({'success': False, 'message': '商品不存在'})
        if item['status'] == 1:
            return jsonify({'success': False, 'message': '已售出商品不能删除'})
        cursor.execute('DELETE FROM Item WHERE item_id = ?', (item_id,))
        conn.commit()
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()


@app.route('/api/buy', methods=['POST'])
def api_buy_item():
    data = request.get_json()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        conn.execute('BEGIN TRANSACTION')

        item = cursor.execute('SELECT status FROM Item WHERE item_id = ?', (data['item_id'],)).fetchone()
        if not item:
            raise Exception('商品不存在')
        if item['status'] == 1:
            raise Exception('商品已售出')

        cursor.execute('UPDATE Item SET status = 1 WHERE item_id = ?', (data['item_id'],))
        cursor.execute(
            'INSERT INTO Orders (order_id, item_id, buyer_id, order_date) VALUES (?, ?, ?, ?)',
            (data['order_id'], data['item_id'], data['buyer_id'], data['order_date'])
        )

        conn.commit()
        return jsonify({'success': True, 'message': '购买成功'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()


if __name__ == '__main__':
    init_database()
    app.run(debug=True, host='0.0.0.0', port=5000)
