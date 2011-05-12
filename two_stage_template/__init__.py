import logging

from google.appengine.ext.webapp import template
from google.appengine.api import memcache

from app import App
import layer_cache
import request_handler
import monkey_patches

def two_pass_handler():
    def decorator(target):
        # Monkey patch up django template
        monkey_patches.patch()

        def wrapper(handler):
            cached_template = TwoPassTemplate.get_first_pass(handler, target)
            handler.response.out.write(cached_template.render_second_pass(handler))

        return wrapper
    return decorator

def two_pass_variable():
    def decorator(target):
        def wrapper(*args, **kwargs):
            first_pass_call = kwargs.get("first_pass_call", True)

            if first_pass_call:
                def inner_wrapper(*args_throwaway, **kwargs_throwaway):
                    logging.critical("setting")
                    memcache.set("some magic key", args[1:], namespace=App.version)
                    return target(*args)
                inner_wrapper.target_name = target.__name__
                return inner_wrapper
            else:
                def inner_wrapper(*args, **kwargs):
                    args_cached = memcache.get("some magic key", namespace=App.version)
                    logging.critical("getting: %s" % args_cached)
                    args = list(args)
                    args.extend(args_cached)
                    return target(*args)
                return inner_wrapper

        return wrapper
    return decorator

class TwoPassTemplate():

    def __init__(self, source, template_value_fxn_names):
        self.source = source
        self.template_value_fxn_names = template_value_fxn_names

    def render_second_pass(self, handler):
        compiled_template = template.Template(self.source)
        second_pass_template_values = {}

        for key in self.template_value_fxn_names:
            wrapped_fxn = getattr(handler, self.template_value_fxn_names[key])
            second_pass_template_values[key] = wrapped_fxn(first_pass_call=False)(handler)

        return compiled_template.render(second_pass_template_values)

    @staticmethod
    def get_first_pass(handler, target):
        template_source, template_value_fxn_names = TwoPassTemplate.render_first_pass(handler, target)
        return TwoPassTemplate(template_source, template_value_fxn_names)

    @staticmethod
#    @layer_cache.cache_with_key_fxn(
#            lambda handler, target: "first_pass_template[%s]" % handler.request.path, 
#            layer=layer_cache.Layers.Memcache
#            )
    def render_first_pass(handler, target):

        template_name, template_values = target(handler)
        template_value_fxn_names = {}

        # Remove callable keys for first pass render,
        # and keep references around for second pass
        for key in template_values.keys():
            if callable(template_values[key]):
                wrapped_fxn = template_values[key]
                wrapped_fxn()
                template_value_fxn_names[key] = wrapped_fxn.target_name
                del template_values[key]

        return (handler.render_template_to_string(template_name, template_values), template_value_fxn_names)

class TwoPassTest(request_handler.RequestHandler):

    @two_pass_variable()
    def sheep(self, monkey):
        return monkey + self.request_int("inc", default=1)

    @two_pass_handler()
    def get(self):

        monkey = 5

        template_values = {
            "sheep": self.sheep(monkey),
            "monkey": "ooh ooh aah aah",
        }

        return ("two_stage_template/two_stage_test.html", template_values)
