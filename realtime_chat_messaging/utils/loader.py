import importlib
import inspect
from django.core.exceptions import ImproperlyConfigured
from rest_framework import serializers
from django.db import models
from channels.db import database_sync_to_async


def import_and_verify_type_class(klass, klass_repr):
    if type(klass) == str:
        module_path, klass_name = klass.rsplit('.', 1)
        module = importlib.import_module(module_path)
        klass = getattr(module, klass_name)
    
    if not inspect.isclass(klass) and not isinstance(klass, serializers) and not isinstance(klass, models):
        raise ImproperlyConfigured(f"{klass_repr} should be a class")
    return klass

def import_and_verify_type_function(func, func_repr):
    if type(func) == str:
        module_path, func_name = func.rsplit('.', 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
    
    if not inspect.isfunction(func) and not isinstance(func, database_sync_to_async):
        raise ImproperlyConfigured(f"{func_repr} should be a function")
    return func
