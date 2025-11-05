import sqlite3
import datetime
import os
import bcrypt
import logging
import json
from contextlib import contextmanager
from threading import Lock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DB_PATH = os.environ.get('DB_PATH', 'nexfi.db')
DB_LOCK = Lock()

# User cache
USER_CACHE = {}
CACHE_TTL = 300


@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_database():
    """Initialize database with tables and indexes"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    date_of_birth TEXT,
                    gender TEXT,
                    profile_pic TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Posts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    content TEXT,
                    image TEXT,
                    likes INTEGER DEFAULT 0,
                    comments_count INTEGER DEFAULT 0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
            
            # Follows table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS follows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    follower_id INTEGER NOT NULL,
                    following_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(follower_id, following_id),
                    FOREIGN KEY (follower_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (following_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
            
            # Messages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user_id INTEGER NOT NULL,
                    to_user_id INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    image TEXT,
                    read INTEGER DEFAULT 0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (from_user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (to_user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
            
            # Create indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_timestamp ON posts(timestamp DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_follows_follower ON follows(follower_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_follows_following ON follows(following_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_from ON messages(from_user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)')
            
            conn.commit()
            logger.info(f"✓ SQLite database initialized at {DB_PATH}")
            
    except Exception as e:
        logger.error(f"✗ Database initialization error: {e}")
        raise


# Initialize database on module load
init_database()


def get_cached_user(user_id):
    """Get user from cache or database"""
    cache_key = str(user_id)
    now = datetime.datetime.utcnow().timestamp()
    
    if cache_key in USER_CACHE:
        data, timestamp = USER_CACHE[cache_key]
        if now - timestamp < CACHE_TTL:
            return data
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, profile_pic FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        
        if row:
            user = dict(row)
            USER_CACHE[cache_key] = (user, now)
            return user
    
    return None


def register_user(username, password, date_of_birth, gender, email, profile_pic=None):
    """Register a new user"""
    try:
        logger.info(f"Registering user: {username}")
        
        # Validation
        if len(username) < 3:
            return False, "Username must be at least 3 characters", None
        if len(password) < 6:
            return False, "Password must be at least 6 characters", None
        
        # Check if username or email exists
        with get_db() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            if cursor.fetchone():
                return False, "Username already exists", None
            
            cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
            if cursor.fetchone():
                return False, "Email already exists", None
            
            # Hash password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            # Insert user
            cursor.execute('''
                INSERT INTO users (username, password, email, date_of_birth, gender, profile_pic)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, hashed_password.decode('utf-8'), email, date_of_birth, gender, profile_pic or ''))
            
            user_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"✓ User registered: {username} (ID: {user_id})")
            return True, "User registered successfully", str(user_id)
            
    except Exception as e:
        logger.error(f"✗ Registration error: {e}")
        return False, str(e), None


def login_user(username, password):
    """Login user"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, password FROM users 
                WHERE username = ? OR email = ?
            ''', (username, username))
            
            user = cursor.fetchone()
            
            if not user:
                return None, "Invalid username/email or password"
            
            user_dict = dict(user)
            
            if bcrypt.checkpw(password.encode('utf-8'), user_dict['password'].encode('utf-8')):
                logger.info(f"✓ Login successful: {username}")
                return str(user_dict['id']), "Login successful"
            else:
                return None, "Invalid username/email or password"
                
    except Exception as e:
        logger.error(f"✗ Login error: {e}")
        return None, str(e)


def create_post(user_id, content, image=None):
    """Create a new post"""
    try:
        if not content and not image:
            return False, "Post must have content or an image"
        
        if content and len(content) > 280:
            return False, "Post content must be 1-280 characters"
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO posts (user_id, content, image)
                VALUES (?, ?, ?)
            ''', (int(user_id), content or '', image or ''))
            
            conn.commit()
            logger.info(f"✓ Post created by user {user_id}")
            return True, "Post created"
            
    except Exception as e:
        logger.error(f"✗ Post creation error: {e}")
        return False, str(e)


def get_feed(user_id, limit=20):
    """Get feed posts"""
    try:
        logger.info(f"⚡ Fetching feed (limit: {limit})")
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get posts with user information
            cursor.execute('''
                SELECT 
                    p.id as post_id,
                    p.user_id,
                    p.content,
                    p.image,
                    p.likes,
                    p.comments_count,
                    p.timestamp,
                    u.username,
                    u.profile_pic
                FROM posts p
                JOIN users u ON p.user_id = u.id
                ORDER BY p.timestamp DESC
                LIMIT ?
            ''', (limit,))
            
            posts = cursor.fetchall()
            
            feed_posts = []
            for post in posts:
                feed_posts.append({
                    "post_id": str(post['post_id']),
                    "user_id": str(post['user_id']),
                    "content": post['content'] or '',
                    "image": post['image'] or '',
                    "likes": post['likes'],
                    "comments_count": post['comments_count'],
                    "timestamp": post['timestamp'],
                    "username": post['username'],
                    "profile_pic": post['profile_pic'] or ''
                })
            
            logger.info(f"✅ Returned {len(feed_posts)} posts")
            return feed_posts, None
            
    except Exception as e:
        logger.error(f"❌ Feed error: {e}")
        return [], str(e)


def get_feed_simple(user_id, limit=20):
    """Fallback feed method (same as primary for SQLite)"""
    return get_feed(user_id, limit)


def follow_user(follower_id, following_username):
    """Follow a user"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get following user ID
            cursor.execute('SELECT id FROM users WHERE username = ?', (following_username,))
            following = cursor.fetchone()
            
            if not following:
                return False, "User not found"
            
            following_id = following['id']
            
            if int(follower_id) == following_id:
                return False, "You cannot follow yourself"
            
            # Check if already following
            cursor.execute('''
                SELECT id FROM follows 
                WHERE follower_id = ? AND following_id = ?
            ''', (int(follower_id), following_id))
            
            if cursor.fetchone():
                return True, f"Already following @{following_username}"
            
            # Create follow relationship
            cursor.execute('''
                INSERT INTO follows (follower_id, following_id)
                VALUES (?, ?)
            ''', (int(follower_id), following_id))
            
            conn.commit()
            logger.info(f"✓ User {follower_id} followed @{following_username}")
            return True, f"Followed @{following_username}"
            
    except Exception as e:
        logger.error(f"✗ Follow error: {e}")
        return False, str(e)


def unfollow_user(follower_id, following_username):
    """Unfollow a user"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get following user ID
            cursor.execute('SELECT id FROM users WHERE username = ?', (following_username,))
            following = cursor.fetchone()
            
            if not following:
                return False, "User not found"
            
            following_id = following['id']
            
            # Delete follow relationship
            cursor.execute('''
                DELETE FROM follows 
                WHERE follower_id = ? AND following_id = ?
            ''', (int(follower_id), following_id))
            
            if cursor.rowcount > 0:
                conn.commit()
                logger.info(f"✓ User {follower_id} unfollowed @{following_username}")
                return True, f"Unfollowed @{following_username}"
            else:
                return False, "You are not following this user"
                
    except Exception as e:
        logger.error(f"✗ Unfollow error: {e}")
        return False, str(e)


def like_post(post_id, increment=True):
    """Like or unlike a post"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            if increment:
                cursor.execute('UPDATE posts SET likes = likes + 1 WHERE id = ?', (int(post_id),))
            else:
                cursor.execute('UPDATE posts SET likes = MAX(0, likes - 1) WHERE id = ?', (int(post_id),))
            
            conn.commit()
            return True, "Like updated"
            
    except Exception as e:
        logger.error(f"✗ Like error: {e}")
        return False, str(e)


def delete_post(post_id, user_id):
    """Delete a post"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM posts 
                WHERE id = ? AND user_id = ?
            ''', (int(post_id), int(user_id)))
            
            if cursor.rowcount > 0:
                conn.commit()
                logger.info(f"✓ Post {post_id} deleted")
                return True, "Post deleted successfully"
            else:
                return False, "Post not found or unauthorized"
                
    except Exception as e:
        logger.error(f"✗ Delete error: {e}")
        return False, str(e)


def get_user_profile(username):
    """Get user profile information"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get user
            cursor.execute('''
                SELECT id, username, email, profile_pic, date_of_birth, gender, created_at
                FROM users WHERE username = ?
            ''', (username,))
            
            user = cursor.fetchone()
            
            if not user:
                return None, "User not found"
            
            user_dict = dict(user)
            
            # Get counts
            cursor.execute('SELECT COUNT(*) as count FROM follows WHERE following_id = ?', (user_dict['id'],))
            followers_count = cursor.fetchone()['count']
            
            cursor.execute('SELECT COUNT(*) as count FROM follows WHERE follower_id = ?', (user_dict['id'],))
            following_count = cursor.fetchone()['count']
            
            cursor.execute('SELECT COUNT(*) as count FROM posts WHERE user_id = ?', (user_dict['id'],))
            posts_count = cursor.fetchone()['count']
            
            profile = {
                "user_id": str(user_dict['id']),
                "username": user_dict['username'],
                "email": user_dict['email'],
                "profile_pic": user_dict['profile_pic'] or '',
                "date_of_birth": user_dict['date_of_birth'] or '',
                "gender": user_dict['gender'] or '',
                "followers_count": followers_count,
                "following_count": following_count,
                "posts_count": posts_count,
                "created_at": user_dict['created_at'] or ''
            }
            
            return profile, None
            
    except Exception as e:
        logger.error(f"✗ Profile error: {e}")
        return None, str(e)


def send_message(from_user_id, to_user_id, text, image=None):
    """Send a message"""
    try:
        if from_user_id == to_user_id:
            return False, "Cannot send message to yourself", None
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO messages (from_user_id, to_user_id, text, image)
                VALUES (?, ?, ?, ?)
            ''', (int(from_user_id), int(to_user_id), text, image or ''))
            
            message_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"✓ Message sent from {from_user_id} to {to_user_id}")
            return True, "Message sent", str(message_id)
            
    except Exception as e:
        logger.error(f"✗ Send message error: {e}")
        return False, str(e), None


def get_messages(user_id, other_user_id, limit=100):
    """Get messages between two users"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, from_user_id, text, image, timestamp, read
                FROM messages
                WHERE (from_user_id = ? AND to_user_id = ?)
                   OR (from_user_id = ? AND to_user_id = ?)
                ORDER BY timestamp ASC
                LIMIT ?
            ''', (int(user_id), int(other_user_id), int(other_user_id), int(user_id), limit))
            
            messages = cursor.fetchall()
            
            message_list = []
            for msg in messages:
                message_list.append({
                    "id": str(msg['id']),
                    "text": msg['text'],
                    "image": msg['image'] or '',
                    "timestamp": msg['timestamp'],
                    "read": bool(msg['read']),
                    "sent_by_me": msg['from_user_id'] == int(user_id)
                })
            
            logger.info(f"✓ Loaded {len(message_list)} messages")
            return message_list, None
            
    except Exception as e:
        logger.error(f"✗ Get messages error: {e}")
        return [], str(e)


def get_user_conversations(user_id):
    """Get all conversations for a user"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get all unique conversation partners
            cursor.execute('''
                SELECT DISTINCT
                    CASE 
                        WHEN from_user_id = ? THEN to_user_id
                        ELSE from_user_id
                    END as other_user_id
                FROM messages
                WHERE from_user_id = ? OR to_user_id = ?
            ''', (int(user_id), int(user_id), int(user_id)))
            
            partners = cursor.fetchall()
            
            result = []
            for partner in partners:
                partner_id = partner['other_user_id']
                
                # Get user info
                cursor.execute('''
                    SELECT username, profile_pic FROM users WHERE id = ?
                ''', (partner_id,))
                user_info = cursor.fetchone()
                
                if not user_info:
                    continue
                
                # Get last message
                cursor.execute('''
                    SELECT text, image, timestamp, from_user_id
                    FROM messages
                    WHERE (from_user_id = ? AND to_user_id = ?)
                       OR (from_user_id = ? AND to_user_id = ?)
                    ORDER BY timestamp DESC
                    LIMIT 1
                ''', (int(user_id), partner_id, partner_id, int(user_id)))
                
                last_msg = cursor.fetchone()
                
                if last_msg:
                    last_message_text = last_msg['text'] or ''
                    if not last_message_text and last_msg['image']:
                        last_message_text = '📷 Photo'
                    
                    result.append({
                        "user_id": str(partner_id),
                        "username": user_info['username'],
                        "profile_pic": user_info['profile_pic'] or '',
                        "last_message": last_message_text,
                        "last_message_time": last_msg['timestamp'],
                        "last_message_sent_by_me": last_msg['from_user_id'] == int(user_id),
                        "last_message_read": True,
                        "unread_count": 0,
                        "online": False
                    })
            
            # Sort by last message time
            result.sort(key=lambda x: x['last_message_time'], reverse=True)
            
            logger.info(f"✓ Loaded {len(result)} conversations")
            return result[:50], None  # Limit to 50
            
    except Exception as e:
        logger.error(f"✗ Get conversations error: {e}")
        return [], str(e)


def mark_messages_read(user_id, other_user_id):
    """Mark messages as read"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE messages 
                SET read = 1
                WHERE from_user_id = ? AND to_user_id = ? AND read = 0
            ''', (int(other_user_id), int(user_id)))
            
            conn.commit()
            return True, "Messages marked as read"
            
    except Exception as e:
        logger.error(f"✗ Mark read error: {e}")
        return False, str(e)


def search_users_by_username(query, limit=20):
    """Search users by username"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, profile_pic
                FROM users
                WHERE username LIKE ?
                ORDER BY username
                LIMIT ?
            ''', (f'%{query}%', limit))
            
            users = cursor.fetchall()
            
            results = []
            for user in users:
                results.append({
                    "user_id": str(user['id']),
                    "username": user['username'],
                    "profile_pic": user['profile_pic'] or ''
                })
            
            logger.info(f"✓ Found {len(results)} users matching '{query}'")
            return results, None
            
    except Exception as e:
        logger.error(f"✗ Search users error: {e}")
        return [], str(e)