from flask import Flask, request, jsonify
from flask_cors import CORS
import db
import logging
import sys
import os
from functools import wraps
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

# CORS configuration
CORS(app, 
     resources={r"/api/*": {
         "origins": ["*"],
         "allow_headers": ["Content-Type", "Authorization"],
         "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         "max_age": 3600
     }}
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Performance monitoring decorator
def log_performance(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        result = f(*args, **kwargs)
        duration = time.time() - start_time
        logger.info(f"⏱️  {f.__name__} took {duration:.2f}s")
        return result
    return decorated_function


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


@app.route('/')
def home():
    return jsonify({"message": "NexFi Backend API is running", "status": "healthy"})


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
        logger.error(f"Register error: {str(e)}", exc_info=True)
        return jsonify({
            "success": False, 
            "message": str(e), 
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
            user = db.users.find_one({"_id": db.ObjectId(user_id)}, {"username": 1})
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
            "message": str(e)
        }), 500


@app.route('/api/post', methods=['POST'])
@log_performance
def post():
    """Create new post"""
    try:
        data = request.json
        
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({"success": False, "message": "user_id required"}), 400
        
        content = data.get('content', '').strip()
        image = data.get('image')
        
        if not content and not image:
            return jsonify({"success": False, "message": "Post must have content or image"}), 400
        
        logger.info(f"📝 Creating post for user {user_id}")
        
        success, message = db.create_post(user_id, content, image)
        
        if success:
            logger.info(f"✅ Post created successfully")
        else:
            logger.error(f"❌ Post creation failed: {message}")
        
        return jsonify({"success": success, "message": message})
        
    except Exception as e:
        logger.error(f"Follow error: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/unfollow', methods=['POST'])
@log_performance
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
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/like', methods=['POST'])
@log_performance
def like():
    """Like/unlike a post"""
    try:
        data = request.json
        success, message = db.like_post(data['post_id'], data['increment'])
        
        return jsonify({"success": success, "message": message})
        
    except Exception as e:
        logger.error(f"Like error: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/delete_post', methods=['POST'])
@log_performance
def delete_post_route():
    """Delete a post"""
    try:
        data = request.json
        success, message = db.delete_post(data['post_id'], data['user_id'])
        
        return jsonify({"success": success, "message": message})
        
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/profile/<username>', methods=['GET'])
@log_performance
def get_profile(username):
    """Get user profile"""
    try:
        profile, error = db.get_user_profile(username)
        
        if error:
            return jsonify({"success": False, "error": error}), 404
        
        return jsonify({"success": True, "profile": profile})
        
    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    try:
        db.client.admin.command('ping')
        
        total_users = db.users.count_documents({}, limit=100000)
        total_posts = db.posts.count_documents({}, limit=100000)
        
        return jsonify({
            "status": "healthy", 
            "db": "connected",
            "users": total_users,
            "posts": total_posts
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@app.route('/api/conversations', methods=['GET'])
@log_performance
def get_conversations():
    """Get all conversations for a user"""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({"conversations": [], "error": "user_id required"}), 400
        
        conversations, error = db.get_user_conversations(user_id)
        
        if error:
            logger.error(f"Conversations error: {error}")
            return jsonify({"conversations": [], "error": error}), 500
        
        logger.info(f"✅ Returning {len(conversations)} conversations")
        return jsonify({"conversations": conversations, "error": None})
        
    except Exception as e:
        logger.error(f"❌ Conversations error: {str(e)}", exc_info=True)
        return jsonify({"conversations": [], "error": str(e)}), 500


@app.route('/api/messages/<other_user_id>', methods=['GET'])
@log_performance
def get_messages(other_user_id):
    """Get messages between users"""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({"messages": [], "error": "user_id required"}), 400
        
        logger.info(f"📨 Fetching messages between {user_id} and {other_user_id}")
        messages, error = db.get_messages(user_id, other_user_id)
        
        if error:
            logger.error(f"Get messages error: {error}")
            return jsonify({"messages": [], "error": error}), 500
        
        logger.info(f"✅ Returning {len(messages)} messages")
        return jsonify({"messages": messages, "error": None})
        
    except Exception as e:
        logger.error(f"❌ Get messages error: {str(e)}", exc_info=True)
        return jsonify({"messages": [], "error": str(e)}), 500


@app.route('/api/messages/send', methods=['POST'])
@log_performance
def send_message():
    """Send a message"""
    try:
        data = request.json
        logger.info(f"📤 Received message send request")
        
        from_user_id = data.get('from_user_id')
        to_user_id = data.get('to_user_id')
        text = data.get('text', '').strip()
        image = data.get('image')
        
        if not from_user_id or not to_user_id:
            return jsonify({"success": False, "message": "Missing user IDs"}), 400
        
        if not text and not image:
            return jsonify({"success": False, "message": "Message must have text or image"}), 400
        
        success, message, msg_id = db.send_message(from_user_id, to_user_id, text, image)
        
        if success:
            logger.info(f"✅ Message sent successfully: {msg_id}")
        else:
            logger.error(f"❌ Failed to send message: {message}")
        
        return jsonify({
            "success": success, 
            "message": message,
            "message_id": msg_id
        })
        
    except Exception as e:
        logger.error(f"❌ Send message error: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/messages/mark_read', methods=['POST'])
@log_performance
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
        logger.error(f"❌ Mark read error: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/search/users', methods=['GET'])
@log_performance
def search_users():
    """Search users"""
    try:
        query = request.args.get('q', '').strip()
        limit = int(request.args.get('limit', 20))
        
        if len(query) < 2:
            return jsonify({"users": []})
        
        logger.info(f"🔍 Searching users: '{query}'")
        users, error = db.search_users_by_username(query, limit)
        
        if error:
            logger.error(f"Search error: {error}")
            return jsonify({"users": [], "error": error}), 500
        
        logger.info(f"✅ Found {len(users)} users")
        return jsonify({"users": users})
        
    except Exception as e:
        logger.error(f"❌ Search error: {str(e)}")
        return jsonify({"users": [], "error": str(e)}), 500


if __name__ == '__main__':
    logger.info("🚀 Starting NexFi Flask server...")
    logger.info("📡 API available at http://0.0.0.0:5000")
    app.run(debug=True, threaded=True)


@app.route('/api/feed', methods=['POST'])
@log_performance
def feed():
    """Get feed - OPTIMIZED"""
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({
                "posts": [], 
                "error": "No user_id provided"
            }), 400
        
        limit = min(data.get('limit', 30), 100)
        
        logger.info(f"📡 Feed request from user {user_id}, limit={limit}")
        
        # Try optimized method first
        posts_list, error = db.get_feed(user_id, limit=limit)
        
        # Fallback to simple method if aggregation fails
        if error and "timeout" in error.lower():
            logger.warning("⚠️  Aggregation timeout, using simple method")
            posts_list, error = db.get_feed_simple(user_id, limit=limit)
        
        if error:
            logger.error(f"❌ Feed error: {error}")
            return jsonify({"posts": [], "error": error}), 500
        
        logger.info(f"✅ Returning {len(posts_list)} posts")
        
        response = jsonify({"posts": posts_list, "error": None})
        response.headers['Cache-Control'] = 'public, max-age=10'
        return response
        
    except Exception as e:
        logger.error(f"❌ Feed route error: {str(e)}", exc_info=True)
        return jsonify({"posts": [], "error": "Server error"}), 500


@app.route('/api/follow', methods=['POST'])
@log_performance
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
        return jsonify({"success": False, "message": str(e)}), 500