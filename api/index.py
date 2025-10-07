from flask import Flask, request, jsonify,render_template
from flask_cors import CORS
from . import db
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": ["*"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": False
    }
})

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response


app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"message": "NexFi Backend API is running 🚀"})



@app.route('/api/register', methods=['POST'])
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
def login():
    """Login user"""
    try:
        data = request.json
        user_id, message = db.login_user(data['username'], data['password'])
        
        # Get the actual username from database
        username = None
        if user_id:
            user = db.users.find_one({"_id": db.ObjectId(user_id)}, {"username": 1})
            if user:
                username = user['username']
        
        return jsonify({
            "success": bool(user_id), 
            "user_id": user_id,
            "username": username,  # Return actual username
            "message": message
        })
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({
            "success": False, 
            "message": str(e)
        }), 500


@app.route('/api/post', methods=['POST'])
def post():
    """Create new post"""
    try:
        data = request.json
        success, message = db.create_post(
            data['user_id'], 
            data.get('content', ''), 
            data.get('image')
        )
        
        return jsonify({"success": success, "message": message})
        
    except Exception as e:
        logger.error(f"Post error: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/feed', methods=['POST'])
def feed():
    """Get global feed - ALL posts from ALL users"""
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({
                "posts": [], 
                "error": "No user_id provided"
            }), 400
        
        # Simple call - just user_id and limit
        posts_list, error = db.get_feed(user_id, limit=100)
        
        logger.info(f"✅ Feed: {len(posts_list)} posts returned to user {user_id}")
        
        return jsonify({"posts": posts_list, "error": error})
        
    except Exception as e:
        logger.error(f"❌ Feed error: {str(e)}", exc_info=True)
        return jsonify({"posts": [], "error": str(e)}), 500


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
        return jsonify({"success": False, "message": str(e)}), 500


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
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/like', methods=['POST'])
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
        db.client.server_info()
        total_posts = db.posts.count_documents({})
        total_users = db.users.count_documents({})
        return jsonify({
            "status": "healthy", 
            "db": "connected",
            "users": total_users,
            "posts": total_posts
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500







logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ... [Keep all your existing routes] ...

# NEW MESSAGING ROUTES - Add these:

@app.route('/api/conversations', methods=['GET'])
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
        
        logger.info(f"✅ Returning {len(conversations)} conversations for user {user_id}")
        return jsonify({"conversations": conversations, "error": None})
        
    except Exception as e:
        logger.error(f"❌ Conversations error: {str(e)}", exc_info=True)
        return jsonify({"conversations": [], "error": str(e)}), 500


@app.route('/api/messages/<other_user_id>', methods=['GET'])
def get_messages(other_user_id):
    """Get messages between current user and another user"""
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
def send_message():
    """Send a message to another user"""
    try:
        data = request.json
        logger.info(f"📤 Received message send request: {data}")
        
        from_user_id = data.get('from_user_id')
        to_user_id = data.get('to_user_id')
        text = data.get('text', '').strip()
        image = data.get('image')
        
        if not from_user_id:
            return jsonify({"success": False, "message": "Missing from_user_id"}), 400
        if not to_user_id:
            return jsonify({"success": False, "message": "Missing to_user_id"}), 400
        
        if not text and not image:
            return jsonify({"success": False, "message": "Message must have text or image"}), 400
        
        logger.info(f"Sending message from {from_user_id} to {to_user_id}: '{text[:50]}'")
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
def search_users():
    """Search users by username"""
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
        logger.error(f"❌ Search users error: {str(e)}")
        return jsonify({"users": [], "error": str(e)}), 500

#
if __name__ == '__main__':
    logger.info("🚀 Starting NexFi Flask server...")
    logger.info("📡 API available at http://0.0.0.0:5000")
    app.run(debug=True)

    app = app
    