from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_caching import Cache
import db
import logging
import sys
import os
from functools import wraps
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

# ULTRA-AGGRESSIVE CORS - Allow everything
CORS(app, 
     resources={r"/*": {
         "origins": "*",
         "allow_headers": "*",
         "methods": "*",
         "max_age": 86400  # 24 hours
     }}
)

# CACHING: In-memory cache for 2 minutes
cache = Cache(app, config={
    'CACHE_TYPE': 'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT': 120  # 2 minutes
})

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Disable Flask request logging for speed
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


# ULTRA-FAST: Performance decorator
def log_performance(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        result = f(*args, **kwargs)
        duration = time.time() - start_time
        if duration > 1.0:  # Only log slow requests
            logger.warning(f"⚠️  {f.__name__} took {duration:.2f}s (SLOW)")
        return result
    return decorated_function


@app.before_request
def before_request():
    g.start = time.time()


@app.after_request
def after_request(response):
    # Minimal CORS headers
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = '*'
    response.headers['Access-Control-Allow-Headers'] = '*'
    
    # Log slow requests
    if hasattr(g, 'start'):
        diff = time.time() - g.start
        if diff > 2.0:
            logger.warning(f"⚠️  Request took {diff:.2f}s")
    
    return response


@app.route('/')
def home():
    return jsonify({"status": "healthy", "message": "NexFi API with PostgreSQL"})


@app.route('/api/register', methods=['POST'])
@log_performance
def register():
    """Register new user"""
    try:
        data = request.json
        
        username = data.get('username')
        password = data.get('password')
        date_of_birth = data.get('date_of_birth')
        gender = data.get('gender')
        email = data.get('email')
        profile_pic = data.get('profile_pic')
        
        if not all([username, password, date_of_birth, gender, email]):
            return jsonify({
                "success": False, 
                "message": "Missing required fields", 
                "user_id": None
            }), 400
        
        success, message, user_id = db.register_user(
            username, password, date_of_birth, gender, email, profile_pic
        )
        
        return jsonify({
            "success": success, 
            "message": message, 
            "user_id": user_id
        })
        
    except Exception as e:
        logger.error(f"Register error: {str(e)}")
        return jsonify({
            "success": False, 
            "message": "Server error", 
            "user_id": None
        }), 500


@app.route('/api/login', methods=['POST'])
@log_performance
def login():
    """Login user"""
    try:
        data = request.json
        user_id, message = db.login_user(data['username'], data['password'])
        
        username = None
        if user_id:
            # Get username from cache or db
            user = db.get_cached_user(int(user_id))
            if user:
                username = user['username']
        
        return jsonify({
            "success": bool(user_id), 
            "user_id": user_id,
            "username": username,  
            "message": message
        })
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({
            "success": False, 
            "message": "Server error"
        }), 500


@app.route('/api/post', methods=['POST'])
@log_performance
def post():
    """Create new post - ULTRA FAST"""
    try:
        data = request.json
        
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({"success": False, "message": "user_id required"}), 400
        
        content = data.get('content', '').strip()
        image = data.get('image')
        
        if not content and not image:
            return jsonify({"success": False, "message": "Post must have content or image"}), 400
        
        success, message = db.create_post(user_id, content, image)
        
        # Clear feed cache immediately
        cache.clear()
        
        return jsonify({"success": success, "message": message})
        
    except Exception as e:
        logger.error(f"Post error: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


@app.route('/api/feed', methods=['POST'])
@log_performance
def feed():
    """ULTRA-FAST feed with aggressive caching"""
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({"posts": [], "error": "No user_id provided"}), 400
        
        limit = min(data.get('limit', 20), 50)  # Default 20, max 50
        
        # CACHE KEY based on limit
        cache_key = f"feed_{limit}"
        
        # Try cache first
        cached_posts = cache.get(cache_key)
        if cached_posts is not None:
            logger.info(f"⚡ CACHE HIT: Returning {len(cached_posts)} posts")
            return jsonify({"posts": cached_posts, "error": None})
        
        logger.info(f"📡 CACHE MISS: Fetching feed (limit={limit})")
        
        # Fetch from database
        posts_list, error = db.get_feed(user_id, limit=limit)
        
        if error:
            logger.error(f"❌ Feed error: {error}")
            return jsonify({"posts": [], "error": error}), 500
        
        # Cache the results
        cache.set(cache_key, posts_list, timeout=120)  # 2 minutes
        
        logger.info(f"✅ Returning {len(posts_list)} posts (cached)")
        
        response = jsonify({"posts": posts_list, "error": None})
        response.headers['Cache-Control'] = 'public, max-age=120'  # 2 minutes
        return response
        
    except Exception as e:
        logger.error(f"❌ Feed error: {str(e)}")
        return jsonify({"posts": [], "error": "Server error"}), 500


@app.route('/api/follow', methods=['POST'])
def follow():
    """Follow a user"""
    try:
        data = request.json
        success, message = db.follow_user(
            data['follower_id'], 
            data['following_username']
        )
        return jsonify({"success": success, "message": message})
    except Exception as e:
        logger.error(f"Follow error: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


@app.route('/api/unfollow', methods=['POST'])
def unfollow():
    """Unfollow a user"""
    try:
        data = request.json
        success, message = db.unfollow_user(
            data['follower_id'], 
            data['following_username']
        )
        return jsonify({"success": success, "message": message})
    except Exception as e:
        logger.error(f"Unfollow error: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


@app.route('/api/like', methods=['POST'])
def like():
    """Like/unlike a post - ULTRA FAST"""
    try:
        data = request.json
        success, message = db.like_post(data['post_id'], data['increment'])
        return jsonify({"success": success, "message": message})
    except Exception as e:
        logger.error(f"Like error: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


@app.route('/api/delete_post', methods=['POST'])
def delete_post_route():
    """Delete a post"""
    try:
        data = request.json
        success, message = db.delete_post(data['post_id'], data['user_id'])
        
        # Clear cache
        if success:
            cache.clear()
        
        return jsonify({"success": success, "message": message})
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


@app.route('/api/profile/<username>', methods=['GET'])
@cache.cached(timeout=300, query_string=True)  # Cache for 5 minutes
def get_profile(username):
    """Get user profile"""
    try:
        profile, error = db.get_user_profile(username)
        
        if error:
            return jsonify({"success": False, "error": error}), 404
        
        return jsonify({"success": True, "profile": profile})
    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        return jsonify({"success": False, "error": "Server error"}), 500


@app.route('/api/health', methods=['GET'])
@cache.cached(timeout=30)  # Cache for 30 seconds
def health():
    """Health check - FAST"""
    try:
        # Test database connection
        conn = db.get_db()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        db.release_db(conn)
        
        return jsonify({
            "status": "healthy", 
            "db": "connected",
            "cache": "enabled"
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@app.route('/api/conversations', methods=['GET'])
@log_performance
def get_conversations():
    """Get all conversations"""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({"conversations": [], "error": "user_id required"}), 400
        
        conversations, error = db.get_user_conversations(user_id)
        
        if error:
            return jsonify({"conversations": [], "error": error}), 500
        
        return jsonify({"conversations": conversations, "error": None})
    except Exception as e:
        logger.error(f"Conversations error: {str(e)}")
        return jsonify({"conversations": [], "error": "Server error"}), 500


@app.route('/api/messages/<other_user_id>', methods=['GET'])
@log_performance
def get_messages(other_user_id):
    """Get messages between users"""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({"messages": [], "error": "user_id required"}), 400
        
        messages, error = db.get_messages(user_id, other_user_id)
        
        if error:
            return jsonify({"messages": [], "error": error}), 500
        
        return jsonify({"messages": messages, "error": None})
    except Exception as e:
        logger.error(f"Get messages error: {str(e)}")
        return jsonify({"messages": [], "error": "Server error"}), 500


@app.route('/api/messages/send', methods=['POST'])
@log_performance
def send_message():
    """Send a message"""
    try:
        data = request.json
        
        from_user_id = data.get('from_user_id')
        to_user_id = data.get('to_user_id')
        text = data.get('text', '').strip()
        image = data.get('image')
        
        if not from_user_id or not to_user_id:
            return jsonify({"success": False, "message": "Missing user IDs"}), 400
        
        if not text and not image:
            return jsonify({"success": False, "message": "Message must have text or image"}), 400
        
        success, message, msg_id = db.send_message(from_user_id, to_user_id, text, image)
        
        return jsonify({
            "success": success, 
            "message": message,
            "message_id": msg_id
        })
    except Exception as e:
        logger.error(f"Send message error: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


@app.route('/api/messages/mark_read', methods=['POST'])
def mark_messages_read():
    """Mark messages as read"""
    try:
        data = request.json
        user_id = data.get('user_id')
        other_user_id = data.get('other_user_id')
        
        if not user_id or not other_user_id:
            return jsonify({"success": False, "message": "Missing user IDs"}), 400
        
        success, message = db.mark_messages_read(user_id, other_user_id)
        
        return jsonify({"success": success, "message": message})
    except Exception as e:
        logger.error(f"Mark read error: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


@app.route('/api/search/users', methods=['GET'])
@cache.cached(timeout=300, query_string=True)  # Cache searches for 5 minutes
def search_users():
    """Search users"""
    try:
        query = request.args.get('q', '').strip()
        limit = int(request.args.get('limit', 20))
        
        if len(query) < 2:
            return jsonify({"users": []})
        
        users, error = db.search_users_by_username(query, limit)
        
        if error:
            return jsonify({"users": [], "error": error}), 500
        
        return jsonify({"users": users})
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return jsonify({"users": [], "error": "Server error"}), 500


# ULTRA-FAST: Options pre-flight handler
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return '', 204


if __name__ == '__main__':
    logger.info("🚀 Starting NexFi Flask server with PostgreSQL...")
    logger.info("⚡ Cache enabled, aggressive optimizations active")
    
    # Production settings
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,  # Disable debug for speed
        threaded=True,
        use_reloader=False  # Disable reloader for speed
    )