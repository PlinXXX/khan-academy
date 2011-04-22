from google.appengine.api import users

from models import UserData
import request_cache
import layer_cache
import models_discussion

@request_cache.cache()
def is_current_user_moderator():
    return users.is_current_user_admin() or UserData.get_for_current_user().moderator

def is_honeypot_empty(request):
    return not request.get("honey_input") and not request.get("honey_textarea")

@request_cache.cache_with_key_fxn(models_discussion.Feedback.memcache_key_for_video)
@layer_cache.cache_with_key_fxn(models_discussion.Feedback.memcache_key_for_video, layer=layer_cache.Layers.Memcache)
def get_feedback_for_video(video):
    feedback_query = models_discussion.Feedback.gql("WHERE targets = :1 AND deleted = :2 AND is_hidden_by_flags = :3", video.key(), False, False)
    return feedback_query.fetch(1000)

def get_feedback_by_type_for_video(video, feedback_type):
    feedbacks = get_feedback_for_video(video)
    return filter(lambda feedback: feedback_type in feedback.types, feedbacks)
