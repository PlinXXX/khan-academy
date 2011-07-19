import logging
import pickle

from mapreduce import control
from mapreduce import operation as op

from models import UserData, UserVideo, UserVideoCss

def backfill_user_data(user_data):
    BATCH_SIZE = 1000
    query_results = True
    cursor = None

    user_video_css = UserVideoCss.get_for_user_data(user_data)
    css_dict = {'started': set([]), 'completed': set([])}

    # Set css for completed videos
    while query_results:
        user_video_query = UserVideo.gql("WHERE user = :1 AND completed = True",
                                         user_data.user)
        if cursor:
            user_video_query.with_cursor(cursor)

        query_results = False
        for user_video in user_video_query.fetch(BATCH_SIZE):
            query_results = True
            css_dict['completed'].add('.v'+str(user_video.video.key().id()))
        cursor = user_video_query.cursor()

    query_results = True
        
    # Set css for started videos
    while query_results:
        user_video_query = UserVideo.gql("WHERE user = :1 AND completed = False", user_data.user)
        if cursor:
            user_video_query.with_cursor(cursor)

        query_results = False
        for user_video in user_video_query.fetch(BATCH_SIZE):
            query_results = True
            css_dict['started'].add('.v'+str(user_video.video.key().id()))
        cursor = user_video_query.cursor()

    user_video_css.pickled_dict = pickle.dumps(css_dict)
    user_video_css.load_pickled()
    user_video_css.version += 1
    user_video_css.put()
        
    logging.info('Completed video_css backfill for %s' % user_data.user)
