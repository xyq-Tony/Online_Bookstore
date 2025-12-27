from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import func, extract
from models import db, Book, Category, Customer, Order, OrderItem
import os, random, re
from datetime import date

# Flask： Python轻量级Web框架
app = Flask(__name__)
# 配置 SQLAlchemy 使用的数据库 URI：cloud_bookstore_real.db
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cloud_bookstore_real.db'
# 设置 Flask 的 SECRET_KEY
app.config['SECRET_KEY'] = 'cloud-key-pro-60-real'
# 禁用 SQLAlchemy 对对象修改的事件追踪
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app) # 将 db（SQLAlchemy 对象）与 Flask 应用绑定

# Login_Manager 用于管理用户登录状态
login_manager = LoginManager(app) 

# 根据 user_id 加载用户
@login_manager.user_loader 
def load_user(user_id):
    """
    根据用户ID加载用户对象
    
    该函数用于Flask-Login扩展，根据提供的用户ID从数据库中查询并返回对应的用户对象。
    通常在用户会话验证或需要获取当前登录用户信息时被调用。
    
    参数:
        user_id (str): 用户的唯一标识符，通常为字符串格式的数字ID
    
    返回值:
        Customer: Customer模型的实例对象，如果用户不存在则返回None
    """
    # 等价于SELECT * FROM customer WHERE id = user_id;
    return Customer.query.get(int(user_id))


# --- 图片服务路由 ---
@app.route('/images/<path:filename>')
def serve_images(filename):
    """
    提供图片文件服务的路由函数
    
    该函数用于处理/images/路径下的文件请求，根据传入的文件路径返回对应的图片文件
    
    参数:
        filename (str): 请求的图片文件路径，包含文件名和可能的子目录路径
    
    返回:
        Response: 指定路径图片文件的响应对象，用于在浏览器中显示或下载图片
    """
    return send_from_directory('images', filename)

# --- API 接口 ---
@app.route('/api/books')
def get_books():
    """
    获取图书列表的API接口
    
    该接口支持分页查询和多种筛选条件，包括分类ID、关键词搜索、出版社和出版年份
    
    参数:
        page (int): 页码，默认为1
        cat_id (int): 分类ID，用于筛选特定分类的图书
        keyword (str): 搜索关键词，用于在书名或作者中搜索
        publisher (str): 出版社名称，用于筛选特定出版社的图书
        year (str): 出版年份，用于筛选特定年份出版的图书
    
    返回:
        JSON: 包含图书列表、总页数、当前页码和总项目数的字典
            - books: 图书对象列表，每个图书对象包含详细信息
            - total_pages: 总页数
            - current_page: 当前页码
            - total_items: 总项目数
    """
    page = request.args.get('page', 1, type=int)
    cat_id = request.args.get('cat_id', type=int)
    keyword = request.args.get('keyword', '')
    publisher = request.args.get('publisher', '')
    year = request.args.get('year', '')
    
    # 构建基础查询对象
    query = Book.query
    # 根据分类ID筛选图书
    # SELECT * FROM book WHERE category_id = ?
    if cat_id: query = query.filter_by(category_id=cat_id)
    # 根据关键词在书名或作者中进行模糊搜索
    # SELECT * FROM book WHERE title LIKE '%keyword%' OR author LIKE '%keyword%'
    if keyword: query = query.filter(Book.title.contains(keyword) | Book.author.contains(keyword))
    # 根据出版社筛选图书
    # SELECT * FROM book WHERE publisher = ?
    if publisher: query = query.filter_by(publisher=publisher)
    # 根据出版年份筛选图书
    # SELECT * FROM book WHERE YEAR(pub_date) = ?
    if year: query = query.filter(extract('year', Book.pub_date) == year)
        
    # 执行分页查询，每页12条记录
    # MySQL等价查询: LIMIT 12 OFFSET ((page-1)*12)
    pagination = query.paginate(page=page, per_page=12, error_out=False) # 改为每页12本，布局更整齐
    
    return jsonify({
        'books': [b.to_dict() for b in pagination.items],
        'total_pages': pagination.pages,
        'current_page': page,
        'total_items': pagination.total
    })

@app.route('/api/filters')
def get_filters():
    """
    获取过滤器数据的API端点
    
    该函数查询数据库中所有不重复的出版商信息，并返回JSON格式的出版商列表。
    
    Args:
        无参数
    
    Returns:
        flask.Response: 返回包含出版商列表的JSON响应，格式为 {'publishers': [publisher1, publisher2, ...]}

    等价mysql查询：
    SELECT DISTINCT publisher 
    FROM books 
    WHERE publisher IS NOT NULL AND publisher != '';
    """
    # 查询数据库中所有不重复的出版商
    publishers = db.session.query(Book.publisher).distinct().all()
    # 构建响应数据，过滤掉空值并返回JSON格式
    return jsonify({'publishers': [p[0] for p in publishers if p[0]]})

@app.route('/api/rankings')
def get_rankings():
    """
    获取销量排行榜前10的书籍
    
    该函数查询数据库中按销量降序排列的前10本书籍，并将结果转换为字典列表返回
    
    Args:
        无参数
    
    Returns:
        flask.Response: JSON格式的响应，包含销量排行榜前10的书籍信息列表
    """
    # 查询按销量降序排列的前10本书籍
    """
    SELECT * 
    FROM book 
    ORDER BY sales_count DESC 降序
    LIMIT 10;
    """
    books = Book.query.order_by(Book.sales_count.desc()).limit(10).all()
    return jsonify([b.to_dict() for b in books])

@app.route('/api/categories')
def get_categories():
    """
    获取分类树的根节点列表（从数据库里找出“所有顶级分类”，然后以 JSON 的形式返回给前端）
    
    该函数查询数据库中所有父分类ID为None的分类项，即分类树的根节点，
    并将这些根节点转换为字典格式返回给前端
    
    Returns:
        Response: JSON格式的响应，包含所有根分类的字典列表
    """
    """
    SELECT * 
    FROM category 
    WHERE parent_id IS NULL;
    """
    roots = Category.query.filter_by(parent_id=None).all()
    return jsonify([c.to_dict() for c in roots])

@app.route('/api/login', methods=['POST'])
def login():
    """
    用户登录接口
    
    该函数处理用户登录请求，验证用户名和密码，如果验证成功则登录用户
    
    参数:
        无显式参数，从请求体中获取JSON数据，包含username和password字段
    
    返回值:
        成功时返回JSON响应: {'msg': '登录成功', 'user': 用户名}，状态码200
        失败时返回JSON响应: {'error': '失败'}，状态码401
    """
    data = request.json
    # 根据用户名查询用户信息
    # SELECT * FROM customer WHERE username = ? LIMIT 1;
    user = Customer.query.filter_by(username=data['username']).first()
    """
    用户表结构
    CREATE TABLE customer (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(80) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL
    );
    """
    # 验证用户存在且密码正确后执行登录
    # 验证用户是否存在  
    # SELECT COUNT(*) FROM customer WHERE username = ?;
    # 完整的用户信息查询（用于密码验证）
    # SELECT id, username, password_hash FROM customer WHERE username = ?;
    if user and user.check_password(data['password']):
        login_user(user)
        return jsonify({'msg': '登录成功', 'user': user.username})
    return jsonify({'error': '失败'}), 401

@app.route('/api/register', methods=['POST'])
def register():
    """
    用户注册接口
    
    该接口接收POST请求，用于新用户注册。检查用户名是否已存在，
    如果不存在则创建新用户并保存到数据库中。
    
    参数:
        无显式参数，从请求体中获取JSON数据，包含username和password字段
    
    返回:
        Response: JSON格式的响应，包含成功或错误信息
                 - 成功时返回: {'msg': 'OK'}, 状态码200
                 - 用户名已存在时返回: {'error': '已存在'}, 状态码400
    """
    data = request.json
    # 检查用户名是否已存在，如果存在则返回错误信息
    # SELECT * FROM customer WHERE username = ? LIMIT 1;
    if Customer.query.filter_by(username=data['username']).first(): return jsonify({'error': '已存在'}), 400
    user = Customer(username=data['username'])
    user.set_password(data['password'])
    # 如果不存在则插入新用户
    # INSERT INTO customer (username, password_hash) VALUES (?, ?);
    db.session.add(user)
    db.session.commit()
    return jsonify({'msg': 'OK'})

@app.route('/api/logout')
@login_required
def logout():
    """
    用户登出接口
    
    该函数处理用户的登出请求，清除用户的登录状态并返回成功响应。
    需要用户已登录才能访问此接口。
    
    参数:
        无参数
    
    返回值:
        Response: JSON格式的响应，包含登出成功的消息
        示例: {"msg": "OK"}
    """
    logout_user()
    return jsonify({'msg': 'OK'})

@app.route('/api/user_info')
def user_info():
    """
    获取用户登录状态信息的API接口
    
    该接口检查当前用户是否已认证登录，如果已登录则返回用户登录状态和用户名，
    如果未登录则仅返回登录状态为False。
    
    Returns:
        flask.jsonify: JSON格式的响应数据
            - 如果用户已登录: {'is_login': True, 'username': current_user.username}
            - 如果用户未登录: {'is_login': False}
    """
    if current_user.is_authenticated: return jsonify({'is_login': True, 'username': current_user.username})
    return jsonify({'is_login': False})

@app.route('/api/order', methods=['POST'])
@login_required
def create_order():
    """
    创建订单接口 - 对应的MySQL语句说明
    
    该函数处理用户提交的订单创建请求，验证商品库存，更新库存和销售数据，
    并将订单信息保存到数据库中。如果库存不足或其他异常情况发生，会回滚事务。
    
    主要执行的MySQL语句包括：
    1. 插入订单记录: INSERT INTO orders (customer_id, total_amount, created_at) VALUES (?, ?, NOW())
    2. 查询图书信息: SELECT * FROM books WHERE id = ?
    3. 更新图书库存: UPDATE books SET stock = stock - ?, sales_count = sales_count + ? WHERE id = ?
    4. 插入订单项: INSERT INTO order_items (order_id, book_id, quantity, price) VALUES (?, ?, ?, ?)
    5. 更新订单总金额: UPDATE orders SET total_amount = ? WHERE id = ?
    """
    items = request.json.get('items', [])
    try:
        # 创建新订单记录，初始总金额为0
        # INSERT INTO orders (customer_id, total_amount, created_at) VALUES (?, 0, NOW())
        order = Order(customer_id=current_user.id, total_amount=0)
        db.session.add(order)
        db.session.flush()
        total = 0
        
        # 遍历订单项，验证库存并计算总金额
        for i in items:
            # 根据ID查询图书信息
            # MySQL等价语句: SELECT * FROM books WHERE id = ? LIMIT 1
            book = Book.query.get(i['id'])
            if book.stock < i['qty']: raise Exception(f"{book.title} 库存不足")
            
            # 更新图书库存和销量
            # MySQL等价语句: UPDATE books SET stock = stock - ?, sales_count = sales_count + ? WHERE id = ?
            book.stock -= i['qty']
            book.sales_count += i['qty']
            total += book.sale_price * i['qty']
            
            # 添加订单项记录
            # MySQL等价语句: INSERT INTO order_items (order_id, book_id, quantity, price) VALUES (?, ?, ?, ?)
            db.session.add(OrderItem(order_id=order.id, book_id=book.id, quantity=i['qty'], price=book.sale_price))
        
        # 更新订单总金额
        # MySQL等价语句: UPDATE orders SET total_amount = ? WHERE id = ?
        order.total_amount = total
        db.session.commit()
        return jsonify({'msg': 'OK', 'id': order.id})
    except Exception as e:
        # 发生异常时回滚数据库事务
        # MySQL等价语句: ROLLBACK
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/my_orders')
@login_required
def my_orders():
    """
    获取当前用户的所有订单信息
    
    该函数查询数据库中属于当前登录用户的所有订单记录，
    按创建时间降序排列，并将订单对象转换为字典格式返回。
    
    SELECT * 
    FROM orders 
    WHERE customer_id = ? 
    ORDER BY created_at DESC;
    """
    # 查询当前用户的所有订单并按创建时间降序排列
    orders = Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).all()
    return jsonify([o.to_dict() for o in orders])

@app.route('/') # 渲染后的index.html模板响应对象
def index(): return render_template('index.html')

# ==========================================
# 构建数据库（60本书）
# ==========================================
def clean_filename(title):
    # 去除书名中的特殊字符作为文件名，避免系统路径错误
    # 例如: "Python编程：从入门..." -> "Python编程从入门..."
    return re.sub(r'[\\/:*?"<>| ：·\s]', '', title) + ".jpg"
# 初始化数据库
def init_data():
    with app.app_context():
        # 删除 所有表
        db.drop_all()
        # 重新建表（根据model）
        db.create_all()
        
        print("正在生成60本全品类书籍数据...")

        # 1. 建立分类树（父分类 → 子分类列表）
        cats_structure = {
            '计算机': ['编程语言', '人工智能', '数据库', '操作系统'],
            '文学': ['中国当代', '外国名著', '悬疑推理', '散文随笔'],
            '历史': ['中国历史', '世界历史', '历史传记', '考古'],
            '经管': ['经济学', '管理学', '投资理财', '市场营销']
        }
        # 缓存数据库生成的 id
        """
        {
        "计算机": 1,
        "编程语言": 2,
        "人工智能": 3,
        "数据库": 4,
        "操作系统": 5......}
        """
        cat_map = {} 
        for root, subs in cats_structure.items(): # root父分类名, subs子分类列表
            parent = Category(name=root)
            db.session.add(parent) # 告诉 SQLAlchemy：这条数据我要存
            db.session.flush() # 立刻执行 INSERT,但不提交事务,拿到 parent.id
            cat_map[root] = parent.id # 记录父分类id
            for s in subs: # 记录该父分类下子分类的id
                sub = Category(name=s, parent_id=parent.id)
                db.session.add(sub)
                db.session.flush()
                cat_map[s] = sub.id

        # 2. 定义60本书的原始数据
        # 格式: (标题, 作者, 子分类, 原价, 出版社)
        raw_books = [
            # --- 计算机 (16本) ---
            ("Python编程——从入门到实践", "Eric Matthes", "编程语言", 89.0, "人民邮电出版社"),
            ("Java核心技术", "Cay S. Horstmann", "编程语言", 119.0, "机械工业出版社"),
            ("C++ Primer Plus", "Stephen Prata", "编程语言", 98.0, "人民邮电出版社"),
            ("Go语言圣经", "Donovan", "编程语言", 79.0, "电子工业出版社"),
            ("JavaScript高级程序设计", "Matt Frisbie", "编程语言", 99.0, "人民邮电出版社"),
            ("Rust编程之道", "张汉东", "编程语言", 85.0, "电子工业出版社"),
            ("机器学习", "周志华", "人工智能", 88.0, "清华大学出版社"),
            ("深度学习", "Ian Goodfellow", "人工智能", 168.0, "人民邮电出版社"),
            ("动手学深度学习", "李沐", "人工智能", 85.0, "人民邮电出版社"),
            ("人工智能：一种现代的方法", "Russell", "人工智能", 128.0, "清华大学出版社"),
            ("数据库系统概念", "Silberschatz", "数据库", 120.0, "机械工业出版社"),
            ("高性能MySQL", "Baron Schwartz", "数据库", 128.0, "电子工业出版社"),
            ("Redis设计与实现", "黄健宏", "数据库", 69.0, "机械工业出版社"),
            ("深入理解计算机系统", "Randal E.Bryant", "操作系统", 139.0, "机械工业出版社"),
            ("现代操作系统", "Tanenbaum", "操作系统", 99.0, "机械工业出版社"),
            ("计算机网络：自顶向下方法", "Kurose", "操作系统", 89.0, "机械工业出版社"),

            # --- 文学 (16本) ---
            ("活着", "余华", "中国当代", 45.0, "北京十月文艺出版社"),
            ("许三观卖血记", "余华", "中国当代", 39.5, "北京十月文艺出版社"),
            ("三体全集", "刘慈欣", "中国当代", 93.0, "重庆出版社"),
            ("平凡的世界", "路遥", "中国当代", 108.0, "北京十月文艺出版社"),
            ("围城", "钱钟书", "中国当代", 39.0, "人民文学出版社"),
            ("百年孤独", "马尔克斯", "外国名著", 55.0, "南海出版公司"),
            ("月亮与六便士", "毛姆", "外国名著", 42.0, "浙江文艺出版社"),
            ("追风筝的人", "胡赛尼", "外国名著", 49.0, "上海人民出版社"),
            ("局外人", "加缪", "外国名著", 45.0, "上海译文出版社"),
            ("白夜行", "东野圭吾", "悬疑推理", 59.0, "南海出版公司"),
            ("嫌疑人X的献身", "东野圭吾", "悬疑推理", 48.0, "南海出版公司"),
            ("福尔摩斯探案全集", "柯南·道尔", "悬疑推理", 128.0, "群众出版社"),
            ("东方快车谋杀案", "阿加莎", "悬疑推理", 39.0, "新星出版社"),
            ("文化苦旅", "余秋雨", "散文随笔", 48.0, "长江文艺出版社"),
            ("撒哈拉的故事", "三毛", "散文随笔", 38.0, "北京十月文艺出版社"),
            ("我与地坛", "史铁生", "散文随笔", 32.0, "人民文学出版社"),

            # --- 历史 (14本) ---
            ("万历十五年", "黄仁宇", "中国历史", 56.0, "中华书局"),
            ("明朝那些事儿", "当年明月", "中国历史", 299.0, "浙江人民出版社"),
            ("中国历代政治得失", "钱穆", "中国历史", 32.0, "三联书店"),
            ("乡土中国", "费孝通", "中国历史", 36.0, "人民出版社"),
            ("人类简史", "赫拉利", "世界历史", 68.0, "中信出版社"),
            ("枪炮、病菌与钢铁", "戴蒙德", "世界历史", 65.0, "上海译文出版社"),
            ("全球通史", "斯塔夫里阿诺斯", "世界历史", 138.0, "北京大学出版社"),
            ("丝绸之路", "彼得·弗兰科潘", "世界历史", 108.0, "浙江大学出版社"),
            ("苏东坡传", "林语堂", "历史传记", 45.0, "湖南文艺出版社"),
            ("曾国藩传", "张宏杰", "历史传记", 68.0, "民主与建设出版社"),
            ("史蒂夫·乔布斯传", "艾萨克森", "历史传记", 88.0, "中信出版社"),
            ("邓小平时代", "傅高义", "历史传记", 108.0, "三联书店"),
            ("中国考古学", "刘莉", "考古", 88.0, "三联书店"),
            ("三星堆之谜", "发现之旅", "考古", 58.0, "巴蜀书社"),

            # --- 经管 (14本) ---
            ("国富论", "亚当·斯密", "经济学", 68.0, "商务印书馆"),
            ("经济学原理", "曼昆", "经济学", 168.0, "北京大学出版社"),
            ("资本论", "马克思", "经济学", 198.0, "人民出版社"),
            ("置身事内", "兰小欢", "经济学", 65.0, "上海人民出版社"),
            ("卓有成效的管理者", "德鲁克", "管理学", 55.0, "机械工业出版社"),
            ("原则", "瑞·达利欧", "管理学", 98.0, "中信出版社"),
            ("金字塔原理", "巴巴拉", "管理学", 68.0, "南海出版公司"),
            ("非暴力沟通", "卢森堡", "管理学", 49.0, "华夏出版社"),
            ("穷爸爸富爸爸", "罗伯特·清崎", "投资理财", 49.0, "四川人民出版社"),
            ("聪明的投资者", "格雷厄姆", "投资理财", 69.0, "人民邮电出版社"),
            ("纳瓦尔宝典", "埃里克", "投资理财", 58.0, "中信出版社"),
            ("营销管理", "科特勒", "市场营销", 168.0, "格致出版社"),
            ("定位", "特劳特", "市场营销", 58.0, "机械工业出版社"),
            ("影响力", "西奥迪尼", "市场营销", 69.0, "北京联合出版公司")
        ]

        expected_files = []

        # 3. 写入数据库
        for item in raw_books:
            title, author, cat_name, price, publisher = item
            
            # 自动生成图片文件名：移除特殊符号，只保留中文和英文数字，加.jpg
            img_name = clean_filename(title)
            expected_files.append(img_name) # 存表修改后的图片文件名

            b = Book(
                title=title, 
                author=author, 
                price=price,
                sale_price=round(price * random.uniform(0.6, 0.9), 1), # 打折
                publisher=publisher,
                pub_date=date(random.choice(range(2018, 2025)), random.randint(1,12), 1),
                pages=random.randint(200, 800),
                language='中文',
                # 数据库存储相对路径
                image_url=f"/images/{img_name}",
                category_id=cat_map[cat_name], # 分类ID
                sales_count=random.randint(0, 2000), # 销量
                stock=random.randint(50, 200) # 库存
            )
            db.session.add(b)
        
        # 管理员（无功能）
        u = Customer(username='admin', email='admin@test.com')
        u.set_password('123456')
        db.session.add(u) # 告诉数据库要存数据
        db.session.commit() # 正式写入数据库

if __name__ == '__main__':
    db_path = os.path.join('instance', 'cloud_bookstore_real.db')
    if not os.path.exists(db_path):
        init_data() # 如果不存在，初始化数据库和数据
    app.run(debug=True)