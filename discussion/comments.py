import os

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from django.utils import simplejson

import models_discussion
from render import render_block_to_string
import util_discussion
import app
import util
import request_handler
import voting

class PageComments(request_handler.RequestHandler):

    def get(self):

        page = 0
        try:
            page = int(self.request.get("page"))
        except:
            pass

        video_key = self.request.get("video_key")
        playlist_key = self.request.get("playlist_key")
        video = db.get(video_key)
        playlist = db.get(playlist_key)

        if video:
            comments_hidden = (self.request.get("comments_hidden") == "1")
            template_values = video_comments_context(video, playlist, page, comments_hidden)
            path = os.path.join(os.path.dirname(__file__), 'video_comments.html')

            html = render_block_to_string(path, 'comments', template_values)
            json = simplejson.dumps({"html": html, "page": page}, ensure_ascii=False)
            self.response.out.write(json)

class AddComment(request_handler.RequestHandler):

    def post(self):

        user = util.get_current_user()

        if not user:
            self.redirect(util.create_login_url(self.request.uri))
            return

        if not util_discussion.is_honeypot_empty(self.request):
            # Honeypot caught a spammer (in case this is ever public or spammers
            # have google accounts)!
            return

        comment_text = self.request.get("comment_text")
        comments_hidden = self.request.get("comments_hidden")
        video_key = self.request.get("video_key")
        playlist_key = self.request.get("playlist_key")
        video = db.get(video_key)

        if comment_text and video:
            if len(comment_text) > 300:
                comment_text = comment_text[0:300] # max comment length, also limited by client

            comment = models_discussion.Feedback()
            comment.author = user
            comment.content = comment_text
            comment.targets = [video.key()]
            comment.types = [models_discussion.FeedbackType.Comment]
            comment.put()

        self.redirect("/discussion/pagecomments?video_key=%s&playlist_key=%s&page=0&comments_hidden=%s" % (video_key, playlist_key, comments_hidden))

def video_comments_context(video, playlist, page=0, comments_hidden=True):

    user = util.get_current_user()

    if page > 0:
        comments_hidden = False # Never hide questions if specifying specific page
    else:
        page = 1

    limit_per_page = 10
    limit_initially_visible = 2 if comments_hidden else limit_per_page

    comments = util_discussion.get_feedback_by_type_for_video(video, models_discussion.FeedbackType.Comment)
    comments = voting.VotingSortOrder.sort(comments)

    count_total = len(comments)
    comments = comments[((page - 1) * limit_per_page):(page * limit_per_page)]

    dict_votes = models_discussion.FeedbackVote.get_dict_for_user_and_video(user, video)
    for comment in comments:
        voting.add_vote_expando_properties(comment, dict_votes)

    count_page = len(comments)
    pages_total = max(1, ((count_total - 1) / limit_per_page) + 1)
    return {
            "user": user,
            "is_mod": util_discussion.is_current_user_moderator(),
            "video": video,
            "playlist": playlist,
            "comments": comments,
            "count_total": count_total,
            "comments_hidden": count_page > limit_initially_visible,
            "limit_initially_visible": limit_initially_visible,
            "pages": range(1, pages_total + 1),
            "pages_total": pages_total,
            "prev_page_1_based": page - 1,
            "current_page_1_based": page,
            "next_page_1_based": page + 1,
            "show_page_controls": pages_total > 1,
            "login_url": util.create_login_url("/video?v=%s" % video.youtube_id)
           }
