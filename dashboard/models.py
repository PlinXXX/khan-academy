import datetime

from google.appengine.ext import db
from google.appengine.ext.db import stats

from counters import user_counter

from itertools import groupby

class DailyStatisticLog(db.Model):
    val = db.IntegerProperty(required=True, default=0)
    dt = db.DateTimeProperty(auto_now_add=True)
    stat_name = db.StringProperty(required=True)

    @staticmethod
    def make_key(stat_name, dt):
        # Use stat name and date (w/ hours/secs/mins stripped) as keyname so we
        # don't record duplicate stats
        return "%s:%s" % (stat_name, dt.date().isoformat())

class DailyStatistic(object):

    @classmethod
    def all(cls):
        return DailyStatisticLog.all().filter("stat_name =", cls.__name__)

    def calc(self):
        raise Exception("Not implemented")

    def name(self):
        # Use subclass name as stat identifier
        stat_name = self.__class__.__name__

        if stat_name == DailyStatistic.__name__:
            raise Exception("DailyStatistic cannot be used directly. Must use an implementing subclass.")

        return stat_name

    def record(self, val = None, dt = None):

        if val is None:
            # Grab actual stat value, implemented by subclass
            val = self.calc()

        if dt is None:
            dt = datetime.datetime.now()

        if val is not None:

            stat_name = self.name()

            return DailyStatisticLog.get_or_insert(
                    key_name = DailyStatisticLog.make_key(stat_name, dt),
                    stat_name = stat_name,
                    val = val,
                    dt = dt,
                    )

        return None

    @staticmethod
    def record_all():

        dt = datetime.datetime.now()

        # Record stats for all implementing subclasses
        for subclass in DailyStatistic.__subclasses__():
            instance = subclass()
            instance.record(dt = dt)

class EntityStatistic(DailyStatistic):
    def __init__(self, kind_name=None):
        self.kind_name = kind_name

    def all(self):
        return DailyStatisticLog.all().filter("stat_name =", self.kind_name)

    # actually updates for all entity kinds
    def record(self, val = None, dt = None):
        kind_stats = [s for s in stats.KindStat.all()]

        logs = []
        kind_stats.sort(key=lambda s: s.kind_name)
        for key, kinds in groupby(kind_stats, lambda s: s.kind_name):
            stat = kinds.next()
            logs.append(DailyStatisticLog(
                key_name=DailyStatisticLog.make_key(stat.kind_name, dt),
                stat_name=stat.kind_name,
                val=stat.count,
                dt=dt
            ))
        db.put(logs)

class RegisteredUserCount(DailyStatistic):
    def calc(self):
        return user_counter.get_count()

# Use ~once-or-twice-a-day-updated google.appengine.ext.db.stats to grab entity count
def get_approximate_entity_count(kind_name):
    kind_stats = stats.KindStat.all().filter("kind_name =", kind_name).fetch(100)

    if kind_stats:
        kind_stats.sort(key = lambda kind_stat: kind_stat.timestamp, reverse=True)
        return kind_stats[0].count

    return None
