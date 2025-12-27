from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Index

db = SQLAlchemy() # 创建数据库对象

"""
分类表（自关联）
CREATE TABLE category (
    id INT AUTO_INCREMENT PRIMARY KEY,  每插入一条新记录，id 会自动加 1
    name VARCHAR(50) NOT NULL,          最多存储 50 个字符的可变长度字符串
    parent_id INT DEFAULT NULL,         默认为空
    CONSTRAINT fk_category_parent       外键约束fk_category_parent：
        FOREIGN KEY (parent_id)             parent_id 是外键
        REFERENCES category(id)             自引用 同 表的 id 列
        ON DELETE SET NULL                  如果父分类被删除，子分类的 parent_id 会自动置为 NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""
class Category(db.Model):
    __tablename__ = 'category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id')) 
    children = db.relationship('Category', backref=db.backref('parent', remote_side=[id]))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'children': [child.to_dict() for child in self.children]
        }
    

"""
book表
CREATE TABLE book (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    author VARCHAR(100) NOT NULL,
    isbn VARCHAR(20) UNIQUE,            不能重复
    price FLOAT NOT NULL,
    sale_price FLOAT DEFAULT NULL,
    stock INT DEFAULT 100,              库存
    sales_count INT DEFAULT 0,          销量
    publisher VARCHAR(100),             出版社
    pub_date DATE,

    pages INT,
    language VARCHAR(20),
    image_url VARCHAR(500),             封面图片链接

    category_id INT NOT NULL,

    CONSTRAINT fk_book_category         外键category_id必须对应 category 表中已有的 id
        FOREIGN KEY (category_id)       如果这个分类下有书籍，不能删除该分类
        REFERENCES category(id)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""
class Book(db.Model):
    __tablename__ = 'book'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    isbn = db.Column(db.String(20), unique=True)
    price = db.Column(db.Float, nullable=False)
    sale_price = db.Column(db.Float)
    stock = db.Column(db.Integer, default=100)
    sales_count = db.Column(db.Integer, default=0)
    publisher = db.Column(db.String(100))
    pub_date = db.Column(db.Date)
    
    # --- 新增属性 ---
    pages = db.Column(db.Integer)        # 页数
    language = db.Column(db.String(20))  # 语言
    
    image_url = db.Column(db.String(500))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    
    __table_args__ = (
        Index('idx_book_sales', 'sales_count'), 
        Index('idx_book_filter', 'publisher', 'pub_date'), # 筛选索引
    )
    
    category = db.relationship('Category', backref='books')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'price': self.price,
            'sale_price': self.sale_price,
            'publisher': self.publisher,
            'pub_year': self.pub_date.year if self.pub_date else '',
            'pages': self.pages,
            'language': self.language,
            'category_name': self.category.name,
            'image': self.image_url
        }



"""
用户表
CREATE TABLE customer (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) UNIQUE,
    password_hash VARCHAR(128)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""
class Customer(UserMixin, db.Model):
    __tablename__ = 'customer'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(128))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)



"""
订单表：
CREATE TABLE orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT,
    total_amount FLOAT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id)
        REFERENCES customer(id)
        ON DELETE SET NULL          如果客户被删除，对应订单的 customer_id 会自动置为 NULL，保留订单记录，但不再关联客户。
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""
class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
    total_amount = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'total_amount': self.total_amount,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'items': [i.to_dict() for i in self.items]
        }

"""
订单明细表：
CREATE TABLE order_item (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT,
    book_id INT,
    quantity INT,
    price FLOAT,    订单项单价

    CONSTRAINT fk_item_order
        FOREIGN KEY (order_id)  外键order_id必须对应 orders 表中已有的 id
        REFERENCES orders(id)
        ON DELETE CASCADE,      如果某个订单被删除，该订单下的所有明细也会自动删除

    CONSTRAINT fk_item_book
        FOREIGN KEY (book_id)   外键book_id必须对应 book 表中已有的 id
        REFERENCES book(id)
        ON DELETE RESTRICT      如果书籍在订单明细中存在，不能删除该书，防止破坏历史订单记录
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""
class OrderItem(db.Model):
    __tablename__ = 'order_item'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'))
    quantity = db.Column(db.Integer)
    price = db.Column(db.Float)
    book = db.relationship('Book')
    
    def to_dict(self):
        return {'book_title': self.book.title, 'quantity': self.quantity, 'price': self.price}
    

"""
建表顺序:
1. category
2. book
3. customer
4. orders
5. order_item

表关系总览：
category
 └─ category (parent_id)

category
 └─ book

customer
 └─ orders  , books
      └─ order_item
            

"""
